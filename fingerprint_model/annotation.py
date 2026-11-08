"""Offline image intake, human review sheet, and audited training export."""
import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

from PIL import Image, ImageOps

from .core import map_label
from .data import read_manifest

FIELDS = ["image_id", "path", "original_path", "sha256", "source_label", "subclass",
          "label", "evidence", "reviewer", "second_label", "second_evidence",
          "second_reviewer", "review_status", "quality_status", "pattern_coverage",
          "group_id", "split", "source", "license", "provenance"]
MAX_FILE = 20 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024
EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


def write_csv(path, rows, fields):
    with Path(path).open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def safe_zip_entries(archive):
    entries, total = [], 0
    for item in archive.infolist():
        name = item.filename.replace("\\", "/")
        parts = PurePosixPath(name).parts
        if name.startswith("/") or ".." in parts or any(":" in p for p in parts):
            raise ValueError("unsafe_zip_path")
        mode = item.external_attr >> 16
        if stat.S_ISLNK(mode) or item.flag_bits & 1:
            raise ValueError("zip_links_or_encryption_not_supported")
        total += item.file_size
        if item.file_size > MAX_FILE or total > MAX_TOTAL:
            raise ValueError("archive_expansion_limit_use_a_smaller_subset")
        if not item.is_dir() and Path(name).suffix.lower() in EXTENSIONS:
            entries.append(item)
    return entries


def canonical_image(raw):
    with Image.open(io.BytesIO(raw)) as image:
        if min(image.size) < 64 or max(image.size) > 8192 or image.width * image.height > 32_000_000:
            raise ValueError("unsupported_image_dimensions")
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("multi_frame_image_not_supported")
        # Preserve the entire pattern; never automatically crop or resize originals.
        image = ImageOps.exif_transpose(image).convert("RGB")
        clean = Image.new("RGB", image.size)
        clean.paste(image)
        return clean


def intake(source, output, license_text, provenance, limit=200):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("output_already_exists")
    if not 1 <= limit <= 2000 or not license_text.strip() or not provenance.strip():
        raise ValueError("invalid_limit_or_missing_provenance")
    if output.is_relative_to(source) and source.is_dir():
        raise ValueError("output_must_be_outside_input_directory")
    archive = None
    if source.is_dir():
        candidates = sorted(p for p in source.rglob("*") if p.suffix.lower() in EXTENSIONS and p.is_file())
        if any(p.is_symlink() or not p.resolve().is_relative_to(source) for p in candidates):
            raise ValueError("input_links_not_supported")
        selected = candidates[:limit]
        sources = [(p.name, p.read_bytes) for p in selected]
    else:
        archive = zipfile.ZipFile(source)
        entries = safe_zip_entries(archive)
        sources = [(item.filename, lambda item=item: archive.read(item)) for item in entries[:limit]]
    rows, failures, seen = [], [], set()
    try:
        output.mkdir(parents=True)
        (output / "originals").mkdir()
        (output / "images").mkdir()
        (output / "previews").mkdir()
        total = 0
        for name, read in sources:
            try:
                if archive is None and selected[len(rows) + len(failures)].stat().st_size > MAX_FILE:
                    raise ValueError("file_size_limit")
                raw = read()
                total += len(raw)
                if len(raw) > MAX_FILE or total > MAX_TOTAL:
                    raise ValueError("intake_size_limit")
                image = canonical_image(raw)
                digest = hashlib.sha256(image.tobytes() + str(image.size).encode()).hexdigest()
                if digest in seen:
                    raise ValueError("duplicate_decoded_image")
                seen.add(digest)
                ident = digest[:24]
                original = f"originals/{ident}{Path(name).suffix.lower()}"
                path = f"images/{ident}.png"
                (output / original).write_bytes(raw)
                image.save(output / path)
                image.thumbnail((500, 500))
                image.save(output / "previews" / f"{ident}.png")
                row = dict.fromkeys(FIELDS, "")
                row.update(image_id=ident, path=path, original_path=original, sha256=digest,
                           review_status="pending", quality_status="pending", pattern_coverage="pending",
                           source="real", license=license_text, provenance=provenance + " | " + name)
                rows.append(row)
            except (ValueError, OSError, Image.DecompressionBombError) as exc:
                failures.append({"file": name, "reason": str(exc)})
        write_csv(output / "annotations.csv", rows, FIELDS)
        (output / "intake-report.json").write_text(json.dumps({"imported": len(rows), "failed": failures,
            "selected": len(sources), "limit": limit, "labels_created": 0}, ensure_ascii=False, indent=2), encoding="utf-8")
        sheet(output / "annotations.csv")
        return {"imported": len(rows), "failed": len(failures), "review": str(output / "review.html")}
    finally:
        if archive:
            archive.close()


def read_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("missing_annotation_columns")
        return list(reader)


def inside(base, relative):
    target = (base / relative).resolve()
    if not target.is_relative_to(base.resolve()):
        raise ValueError("path_outside_annotation_folder")
    return target


def sheet(csv_path):
    csv_path = Path(csv_path).resolve()
    cards = []
    rows = read_rows(csv_path)
    for index, row in enumerate(rows):
        inside(csv_path.parent, row["path"])
        ident = html.escape(row["image_id"])
        path = html.escape(row["path"], quote=True)
        provenance_parts = row["provenance"].split(" | ")
        source_name = html.escape(provenance_parts[1] if len(provenance_parts) > 1 else provenance_parts[0])
        cards.append(f'<article data-index="{index}"><a href="{path}" target="_blank"><img src="{path}" loading="lazy"></a><p>{ident}</p><p>出典内のパス: {source_name}</p><div class="fields"></div></article>')
    document = '<!doctype html><meta charset="utf-8"><title>Local fingerprint review</title>'
    document += '<style>body{font-family:sans-serif}main{display:flex;flex-wrap:wrap}article{width:min(440px,95vw);margin:12px;border:1px solid #aaa;padding:8px}img{width:100%;height:340px;object-fit:contain}p{overflow-wrap:anywhere}label{display:block;margin:6px}input,select{max-width:95%}button{padding:12px;position:sticky;top:0}</style>'
    document += '<h1>ローカル確認用 — 正解ラベルは未作成</h1><p>画像をクリックすると全画像。画像端で見えないdeltaは「存在しない」と判定しない。未確定はpending/unknown。保存ボタンでCSVをダウンロードし、このHTMLと同じフォルダへ移動してください。画面を閉じる前に保存。</p><button id="save">レビューCSVを保存</button><main>'
    script = r'''
<script>
const rows=ROWS, columns=COLUMNS;
const fields=[['label','担当1の分類',['','arch','loop','whorl','unknown']],['subclass','亜型（分かる場合）',null],['evidence','担当1の根拠（recurve/delta/隆線等）',null],['reviewer','担当1の仮名ID',null],['second_label','担当2の分類',['','arch','loop','whorl','unknown']],['second_evidence','担当2の根拠',null],['second_reviewer','担当2の仮名ID',null],['review_status','レビュー状態',['pending','provisional','agreed','disputed','unknown']],['quality_status','模様を読める品質',['pending','pass','fail']],['pattern_coverage','必要な模様範囲',['pending','sufficient','morphology_only','insufficient']],['group_id','同一人物/家族の仮名ID',null],['split','グループの分割',['','train','validation','test']]];
document.querySelectorAll('article').forEach(card=>{const row=rows[Number(card.dataset.index)]; fields.forEach(([key,title,options])=>{const label=document.createElement('label');label.textContent=title+' ';const input=document.createElement(options?'select':'input');if(options)options.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v||'未記入';input.append(o)});input.value=row[key]||'';input.addEventListener('change',()=>{row[key]=input.value;window.onbeforeunload=()=>true});label.append(input);card.querySelector('.fields').append(label)})});
document.querySelector('#save').onclick=()=>{const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';const csv='\ufeff'+[columns,...rows.map(r=>columns.map(c=>r[c]))].map(r=>r.map(quote).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='annotations-reviewed.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);window.onbeforeunload=null};
</script>'''
    script = script.replace("ROWS", json.dumps(rows, ensure_ascii=False).replace("<", "\\u003c"))
    script = script.replace("COLUMNS", json.dumps(FIELDS))
    (csv_path.parent / "review.html").write_text(document + "".join(cards) + "</main>" + script, encoding="utf-8")


def export(csv_path, filename="manifest-reviewed.csv", allow_provisional=False, preprocessing="none"):
    csv_path = Path(csv_path).resolve()
    output = inside(csv_path.parent, filename)
    if output.exists() or output.with_suffix(".audit.json").exists():
        raise ValueError("export_already_exists")
    selected, excluded, groups = [], [], {}
    for row in read_rows(csv_path):
        group, split = row["group_id"].strip(), row["split"].strip()
        if group and split:
            if split not in {"train", "validation", "test"}:
                raise ValueError("invalid_split")
            if group in groups and groups[group] != split:
                raise ValueError("group_leakage")
            groups[group] = split
        provisional = allow_provisional and row["review_status"] == "provisional"
        coverage_ok = row["pattern_coverage"] == "sufficient" or (provisional and row["pattern_coverage"] == "morphology_only")
        if (row["review_status"] != "agreed" and not provisional) or row["quality_status"] != "pass" or not coverage_ok:
            excluded.append(row["image_id"])
            continue
        required = ["evidence", "reviewer", "group_id", "split", "license", "provenance"]
        if not provisional:
            required += ["second_evidence", "second_reviewer"]
        if not all(row[k].strip() for k in required):
            raise ValueError("agreed_row_missing_evidence_or_group")
        if not provisional and row["reviewer"].strip().casefold() == row["second_reviewer"].strip().casefold():
            raise ValueError("two_distinct_reviewers_required")
        label = map_label(row["label"])
        if not provisional and label != map_label(row["second_label"]):
            raise ValueError("reviewers_disagree")
        if row["subclass"].strip() and map_label(row["subclass"]) != label:
            raise ValueError("subclass_label_mismatch")
        if row["source"] != "real":
            raise ValueError("this_export_is_for_real_data")
        image_path = inside(csv_path.parent, row["path"])
        if image_path.stat().st_size > MAX_FILE:
            raise ValueError("reviewed_image_size_limit")
        image = canonical_image(image_path.read_bytes())
        digest = hashlib.sha256(image.tobytes() + str(image.size).encode()).hexdigest()
        if digest != row["sha256"]:
            raise ValueError("image_changed_since_intake_reimport_and_review")
        if provisional:
            row["provenance"] += " | SINGLE-REVIEW-PROVISIONAL"
            if row["pattern_coverage"] == "morphology_only":
                row["provenance"] += " | MORPHOLOGY-ONLY: fine pattern details unverified"
        selected.append({k: (label if k == "label" else row[k]) for k in
                         ["path", "label", "group_id", "split", "source", "license", "provenance"]})
    # Validate all class/split coverage, quality and duplicate checks before publishing manifest.
    temp = csv_path.parent / (filename + ".checking")
    if temp.exists():
        raise ValueError("temporary_export_exists")
    try:
        write_csv(temp, selected, ["path", "label", "group_id", "split", "source", "license", "provenance"])
        read_manifest(temp, preprocessing=preprocessing)
        temp.rename(output)
    finally:
        if temp.exists():
            temp.unlink()
    audit = {"annotations_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
             "selected": len(selected), "excluded": excluded, "preprocessing": preprocessing,
             "policy": "provisional-experiment" if allow_provisional else "two-reviewer-agreement; full-pattern; quality-pass"}
    output.with_suffix(".audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return {"manifest": str(output), **audit}


def main():
    parser = argparse.ArgumentParser(description="Offline human annotation; never creates ground truth automatically")
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("--input", required=True)
    imp.add_argument("--output", required=True)
    imp.add_argument("--license", required=True)
    imp.add_argument("--provenance", required=True)
    imp.add_argument("--limit", type=int, default=200)
    for command in ("sheet", "export"):
        p = sub.add_parser(command)
        p.add_argument("--csv", required=True)
        if command == "export":
            p.add_argument("--allow-provisional", action="store_true")
            p.add_argument("--preprocessing", choices=["none", "autocontrast-1pct"], default="none")
    args = parser.parse_args()
    try:
        if args.command == "import":
            result = intake(args.input, args.output, args.license, args.provenance, args.limit)
        elif args.command == "sheet":
            result = sheet(args.csv)
        else:
            result = export(args.csv, allow_provisional=args.allow_provisional, preprocessing=args.preprocessing)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "error", "reason": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
