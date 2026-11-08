"""Experimental masked ridge-orientation pipeline; not biometric identification."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .core import LABELS

VERSION = "masked-local-orientation-v1"
SIZE = 512
GRID = 16


def largest_component(mask):
    """Small 128px grid flood fill; selects largest foreground component."""
    seen = np.zeros_like(mask, dtype=bool)
    best = []
    h, w = mask.shape
    for y, x in zip(*np.where(mask)):
        if seen[y, x]:
            continue
        seen[y, x] = True
        stack = [(int(y), int(x))]; component = []
        while stack:
            yy, xx = stack.pop(); component.append((yy, xx))
            for ny, nx in ((yy-1,xx),(yy+1,xx),(yy,xx-1),(yy,xx+1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx] = True; stack.append((ny,nx))
        if len(component) > len(best):
            best = component
    result = np.zeros_like(mask, dtype=np.uint8)
    for y,x in best: result[y,x] = 255
    return Image.fromarray(result)


def canonicalize(image, domain):
    if domain not in {"scan", "phone"}: raise ValueError("domain_must_be_scan_or_phone")
    rgb = ImageOps.exif_transpose(image).convert("RGB")
    small = rgb.resize((128,128),Image.Resampling.BILINEAR)
    a = np.asarray(small,dtype=np.float32)/255
    gray = np.asarray(small.convert("L"),dtype=np.float32)/255
    if domain == "phone":
        # Explicit heuristic for these RGB development photos; not a universal skin detector.
        center_green=float(np.median(a[38:90,38:90,1]))
        raw_mask = (a[:,:,0] > a[:,:,1]*1.06) & (a[:,:,0] > a[:,:,2]*1.10) & ((a.max(2)-a.min(2)) > .08) & (a[:,:,1] > .3*center_green)
    else:
        normalized = np.asarray(ImageOps.autocontrast(small.convert("L"),cutoff=1),dtype=np.float32)/255
        raw_mask = normalized < .82
    mask = Image.fromarray(np.uint8(raw_mask)*255).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    mask = largest_component(np.asarray(mask)>0)
    if np.count_nonzero(np.asarray(mask)) < 128*128*.06:
        raise ValueError("insufficient_foreground_retake_or_adjust_roi")
    bbox = mask.getbbox()
    sx,sy=rgb.width/128,rgb.height/128
    x0,y0,x1,y1=bbox
    box=(max(0,int((x0-3)*sx)),max(0,int((y0-3)*sy)),min(rgb.width,int((x1+3)*sx)),min(rgb.height,int((y1+3)*sy)))
    foreground = rgb.convert("L").crop(box)
    full_mask=mask.resize(rgb.size,Image.Resampling.NEAREST).crop(box)
    side=max(foreground.size)
    canvas=Image.new("L",(side,side),255); padded_mask=Image.new("L",(side,side),0)
    offset=((side-foreground.width)//2,(side-foreground.height)//2)
    canvas.paste(foreground,offset);padded_mask.paste(full_mask,offset)
    canvas=canvas.resize((SIZE,SIZE),Image.Resampling.BILINEAR)
    padded_mask=padded_mask.resize((SIZE,SIZE),Image.Resampling.NEAREST)
    return canvas,padded_mask,{"domain":domain,"foreground_bbox_in_roi":list(box),
                               "segmentation":"heuristic color" if domain=="phone" else "heuristic scan intensity"}


def descriptor(gray, mask):
    gray=gray.convert("L"); mask=mask.convert("L")
    smooth=np.asarray(gray.filter(ImageFilter.GaussianBlur(.6)),dtype=np.float32)/255
    illumination=np.asarray(gray.filter(ImageFilter.GaussianBlur(12)),dtype=np.float32)/255
    residual=smooth-illumination
    interior=np.asarray(mask.filter(ImageFilter.MinFilter(17)))>0
    gy,gx=np.gradient(residual)
    def pool(v):return v.reshape(GRID,32,GRID,32).mean(axis=(1,3))
    xx,yy,xy=pool(gx*gx),pool(gy*gy),pool(gx*gy)
    energy=xx+yy
    coherence=np.sqrt((xx-yy)**2+4*xy**2)/(energy+1e-9)
    angle=np.stack(((xx-yy)/(energy+1e-9),2*xy/(energy+1e-9)),axis=-1)
    coverage=pool(interior.astype(np.float32))
    foreground_energy=energy[coverage>.5]
    if not len(foreground_energy):raise ValueError("no_interior_foreground")
    noise_floor=max(float(np.quantile(foreground_energy,.15)),1e-6)
    valid=(coverage>.85)&(energy>noise_floor)&(coherence>.25)
    weights=np.where(valid,coherence,0).astype(np.float32)
    vector=(angle*weights[:,:,None]).ravel().astype(np.float32)
    quality={"valid_blocks":int(valid.sum()),"interior_blocks":int((coverage>.85).sum()),
             "mean_coherence":float(coherence[valid].mean()) if valid.any() else 0.,
             "readable":bool(valid.sum()>=24),"note":"Ridge-direction coverage heuristic, not proof of a fingerprint or correct pattern."}
    preview=np.uint8(np.clip(.5+residual*4,0,1)*255)
    return {"vector":vector,"angles":angle.reshape(-1,2).astype(np.float32),"weights":weights.ravel(),
            "quality":quality,"normalized":Image.fromarray(preview),"mask":mask}


def extract(path, domain, roi=None):
    from io import BytesIO
    if domain not in ('phone','scan'):raise ValueError('invalid_domain')
    if isinstance(path,bytes):
        if len(path)>20*1024*1024:raise ValueError('image_size_limit')
        source=BytesIO(path)
    else:
        path=Path(path)
        if path.stat().st_size > 20*1024*1024:raise ValueError("image_size_limit")
        source=path
    with Image.open(source) as opened:
        if opened.format not in ('PNG','JPEG'):raise ValueError('unsupported_image_format')
        if getattr(opened,'n_frames',1)!=1:raise ValueError('multiple_frames_unsupported')
        if max(opened.size)>8192 or min(opened.size)<64 or opened.width*opened.height>32000000:
            raise ValueError('unsupported_image_dimensions')
        im=ImageOps.exif_transpose(opened).convert("RGB")
        if max(im.size)>8192 or min(im.size)<64:raise ValueError("unsupported_image_dimensions")
        if roi is not None:
            if len(roi)!=4 or not (0<=roi[0]<roi[2]<=im.width and 0<=roi[1]<roi[3]<=im.height):
                raise ValueError("invalid_manual_roi")
            im=im.crop(tuple(roi))
        gray,mask,info=canonicalize(im,domain)
    result=descriptor(gray,mask)
    return {**result,"gray":gray,"segmentation":info,"manual_roi":roi}


def variants(item):
    yield item
    for angle,dx,dy in [(-8,-12,0),(-4,0,12),(4,0,-12),(8,12,0)]:
        gray=Image.new("L",(576,576),255);mask=Image.new("L",(576,576),0)
        gray.paste(item["gray"],(32+dx,32+dy));mask.paste(item["mask"],(32+dx,32+dy))
        gray=gray.rotate(angle,resample=Image.Resampling.BILINEAR,expand=True,fillcolor=255).resize((512,512),Image.Resampling.BILINEAR)
        mask=mask.rotate(angle,resample=Image.Resampling.NEAREST,expand=True,fillcolor=0).resize((512,512),Image.Resampling.NEAREST)
        yield descriptor(gray,mask)


def template_scores(item, angles, weights, labels):
    common=np.minimum(weights,item["weights"][None,:])
    # Doubled-angle vectors are polarity invariant; compare only mutually readable blocks.
    dots=np.sum(angles*item["angles"][None,:,:],axis=2)
    norm=np.linalg.norm(angles,axis=2)*np.linalg.norm(item["angles"],axis=1)[None,:]
    disagreement=1-dots/(norm+1e-8)
    distance=(common*disagreement).sum(1)/(common.sum(1)+1e-8)
    distance=np.where((common>0).sum(1)>=16,distance,2.)
    class_distance=np.array([np.sort(distance[labels==c])[:3].mean() if np.any(labels==c) else 2 for c in range(3)])
    similarity=np.exp(-4*(class_distance-class_distance.min()));similarity/=similarity.sum()
    return similarity,class_distance


def save_templates(path,items,labels,metadata):
    path=Path(path)
    if path.exists():raise ValueError("model_already_exists")
    np.savez_compressed(path,angles=np.stack([i["angles"] for i in items]),weights=np.stack([i["weights"] for i in items]),
                        labels=np.asarray(labels,dtype=np.int64),metadata=np.array(json.dumps({**metadata,"version":VERSION,"labels":list(LABELS)})))


def load_templates(path):
    with np.load(path,allow_pickle=False) as f:
        metadata=json.loads(str(f["metadata"].item()));angles=f["angles"].copy();weights=f["weights"].copy();labels=f["labels"].copy()
    if metadata.get("version")!=VERSION or metadata.get("labels")!=list(LABELS):raise ValueError("unsupported_pattern_model")
    if angles.shape!=(len(labels),256,2) or weights.shape!=(len(labels),256) or labels.dtype.kind not in 'iu' or set(labels.tolist())!={0,1,2}:
        raise ValueError("invalid_template_arrays")
    if not np.isfinite(angles).all() or not np.isfinite(weights).all() or (weights<0).any() or (weights>1).any():raise ValueError("invalid_template_values")
    return angles,weights,labels,metadata


def predict(item,model):
    angles,weights,labels,metadata=model
    if not item['quality']['readable']:
        return {"candidate":None,"decision":"retake","verified_label":None,"quality":item['quality'],
                "reasons":["insufficient_readable_direction_blocks"],"method":VERSION,"experimental":True}
    p,d=template_scores(item,angles,weights,labels)
    if float(d.min()) >= 1.999:
        return {"candidate":None,"decision":"insufficient_match","verified_label":None,"quality":item['quality'],
                "reasons":["insufficient_common_readable_blocks_with_all_classes"],"method":VERSION,"experimental":True}
    order=np.argsort(d);margin=float(d[order[1]]-d[order[0]])
    return {"candidate":LABELS[int(order[0])],"decision":"reference_candidate","verified_label":None,
            "quality":item['quality'],"support_margin":margin,"class_distances":dict(zip(LABELS,d.tolist())),
            "relative_similarity":dict(zip(LABELS,p.tolist())),"reasons":["single_AI_scan_labels","phone_domain_not_validated"]+
            (["close_competing_patterns"] if margin<.08 else []),"method":VERSION,"experimental":True,
            "warning":"Reference ranking only. Similarities are not correctness probabilities; no verified class."}


def train_templates(manifest,lock_path,output,evaluation_plan=None):
    from .audit import verify_lock
    from .data import read_manifest
    lock=verify_lock(manifest,lock_path)
    plan_hash=None
    if evaluation_plan:
        plan=json.loads(Path(evaluation_plan).read_text(encoding='utf-8'))
        if plan.get('manifest_sha256')!=lock['manifest_sha256']:
            raise ValueError('evaluation_plan_manifest_mismatch')
        plan_hash=hashlib.sha256(Path(evaluation_plan).read_bytes()).hexdigest()
    prepared=read_manifest(manifest,preprocessing='autocontrast-1pct',excluded_splits=('test',))
    base=Path(manifest).resolve().parent
    items=[];labels=[]
    for row,label,_ in prepared:
        item=extract(base/row['path'],'scan')
        if not item['quality']['readable']:
            raise ValueError('unreadable_development_training_image')
        derived=list(variants(item));items.extend(derived);labels.extend([label]*len(derived))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    save_templates(output,items,labels,{'domain':'scan-provisional','development_rows':len(prepared),
        'manifest_sha256':lock['manifest_sha256'],'old_test_excluded':sum(r['split']=='test' for r in lock['rows']),
        'partition_lock_sha256':hashlib.sha256(Path(lock_path).read_bytes()).hexdigest(),
        'evaluation_plan_sha256':plan_hash,
        'selection':'Exploratory templates from train+validation only; no final phone validation'})
    return {'model':str(output),'development_rows':len(prepared),'templates':len(items),'version':VERSION}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    pr=sub.add_parser('predict')
    pr.add_argument('--model',required=True);pr.add_argument('--image',required=True)
    pr.add_argument('--domain',choices=['scan','phone'],required=True)
    pr.add_argument('--roi',help='Manual EXIF-oriented x0,y0,x1,y1; not automatic whole-image finger detection')
    tr=sub.add_parser('train')
    tr.add_argument('--manifest',required=True);tr.add_argument('--lock',required=True);tr.add_argument('--output',required=True)
    tr.add_argument('--evaluation-plan',help='Optional fixed CV-plan provenance; must match manifest hash')
    args=parser.parse_args()
    try:
        if args.command=='train':
            print(json.dumps(train_templates(args.manifest,args.lock,args.output,args.evaluation_plan),indent=2));return 0
        roi=[int(x) for x in args.roi.split(',')] if args.roi else None
        item=extract(args.image,args.domain,roi)
        print(json.dumps(predict(item,load_templates(args.model)),indent=2))
    except (ValueError,OSError,KeyError) as exc:
        if str(exc) in {'insufficient_foreground_retake_or_adjust_roi','no_interior_foreground'}:
            print(json.dumps({'candidate':None,'verified_label':None,'decision':'retake','reasons':[str(exc)],'experimental':True}));return 0
        print(json.dumps({'decision':'error','reason':str(exc)}),file=sys.stderr);return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
