import { Music } from './lib/music.js'
import { validateImageWithBackend } from './api.js'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import './v13.css'
import './v14.css'

const PARTICIPANT_LABELS = ['A', 'B', 'C']
const GENRES = [
  { id: 'pop', label: 'POP' },
  { id: 'lofi', label: 'LO-FI' },
  { id: 'electronic', label: 'ELECTRO' },
]
const THEMES = [
  { id: 'scarlet', name: 'Scarlet Red', detail: '赤 × 黒' },
  { id: 'violet', name: 'Violet Pulse', detail: '紫 × 黒' },
  { id: 'ice', name: 'Ice Signal', detail: 'シアン × 深緑' },
  { id: 'cobalt', name: 'Cobalt Blue', detail: '青 × ネイビー' },
  { id: 'amber', name: 'Golden Hour', detail: '黄金 × 黒' },
  { id: 'emerald', name: 'Emerald Beat', detail: '緑 × 黒' },
  { id: 'pink', name: 'Pink Tempo', detail: '桃 × 濃紺' },
  { id: 'silver', name: 'Mono Vinyl', detail: '白 × グレー' },
]

function createId(prefix = 'id') {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`
}

const PATTERN_GENRE = {arch:'ヒップホップ', loop:'ハウス', whorl:'テクノ'}

function buildTrack(players, kind) {
  // Keep displayed observations intact; bound only the musical tempo input.
  const musicalPlayers = players.map(p => ({...p, feature: {...p.feature,
    ridgeCount: Math.max(32, Math.min(64, p.feature.ridgeCount)),
  }}))
  const score = Music.compose(musicalPlayers)
  const pcm = Music.render(score)
  const audioUrl = URL.createObjectURL(new Blob([Music.wav(pcm)], {type:'audio/wav'}))
  const ids = players.map((p) => p.id)
  return {
    id: createId(kind === 'individual' ? 'solo' : 'ensemble'),
    type: kind,
    title: kind === 'individual' ? `${ids[0]}'s Motif` : `${ids.join(' + ')} Ensemble`,
    subtitle: `${score.genre} / ${score.bpm} BPM（音楽用に80〜160へ調整・参考推定）`,
    participants: ids,
    genre: score.genre,
    accent: score.genre,
    audioUrl,
    scoreInfo: { bpm: score.bpm, method: score.method, pattern: score.pattern },
  }
}

function analyzeFingerprint(file, onProgress, cropRatio = 1) {
  return new Promise(async (resolve, reject) => {
    let worker, timeout, bitmap
    try {
      if (!['image/jpeg','image/png','image/webp'].includes(file.type)) throw Error('JPEG・PNG・WebP画像を選んでください。')
      if (file.size > 10*1024*1024) throw Error('画像は10MB以下にしてください。')
      bitmap = await createImageBitmap(file)
      if (bitmap.width < 192 || bitmap.height < 192 || bitmap.width > 8192 || bitmap.height > 8192) throw Error('画像の縦横は192〜8192pxにしてください。')
      const canvas = document.createElement('canvas')
      canvas.width = 384; canvas.height = 384
      const ctx = canvas.getContext('2d', {willReadFrequently:true})
      if (!ctx) throw Error('画像解析の準備に失敗しました。')
      const cropSide = Math.min(bitmap.width, bitmap.height) * cropRatio
      const sw = cropRatio < 1 ? cropSide : bitmap.width
      const sh = cropRatio < 1 ? cropSide : bitmap.height
      const sx = (bitmap.width - sw) / 2, sy = (bitmap.height - sh) / 2
      const scale = Math.min(384 / sw, 384 / sh)
      const w = sw * scale, h = sh * scale
      ctx.fillStyle = '#ffffff'; ctx.fillRect(0,0,384,384)
      ctx.drawImage(bitmap, sx, sy, sw, sh, (384-w)/2, (384-h)/2, w,h)
      const pixels = ctx.getImageData(0,0,384,384).data
      worker = new Worker(`${import.meta.env.BASE_URL}analysis-worker.js`)
      const finish = (error, data) => {clearTimeout(timeout); worker.terminate(); error ? reject(error) : resolve(data)}
      timeout = setTimeout(() => finish(Error('解析に時間がかかりすぎました。画像を確認して再試行してください。')),30000)
      worker.onmessage = ({data}) => {
        if(data.stage) {onProgress(data.stage); return}
        if(data.error) {finish(Error(data.error)); return}
        if(data.result) {
          const {preview, ...feature} = data.result
          // preview contains image-derived pixels; do not retain those in React state.
          finish(null, feature)
        }
      }
      worker.onerror = () => finish(Error('画像解析に失敗しました。'))
      worker.postMessage({pixels, width:384, height:384}, [pixels.buffer])
    } catch(error) {if(worker) worker.terminate();clearTimeout(timeout);reject(error)}
    finally {if(bitmap) bitmap.close()}
  })
}

function FingerprintIcon() {
  return (
    <svg className="fingerprint-icon" viewBox="0 0 200 220" fill="none" aria-hidden="true">
      <g stroke="currentColor" strokeWidth="7" strokeLinecap="round">
        <path d="M100 20C48 20 15 58 15 104" />
        <path d="M185 104C185 58 152 20 100 20" />
        <path d="M34 120V104C34 65 61 39 100 39S166 65 166 104V133" />
        <path d="M52 143V104C52 77 71 56 100 56S148 77 148 104V147" />
        <path d="M69 159V105C69 88 81 74 100 74S131 88 131 105V159" />
        <path d="M86 174V106C86 98 92 92 100 92S114 98 114 106V176" />
        <path d="M100 106V188" />
      </g>
    </svg>
  )
}

function App() {
  const hiddenFileInputRef = useRef(null)
  const audioContextRef = useRef(null)
  const playbackTimerRef = useRef(null)
  const audioElementRef = useRef(null)
  const tracksForCleanupRef = useRef([])
  const generationTokenRef = useRef({A:0,B:0,C:0})
  const uploadTokenRef = useRef({A:0,B:0,C:0})
  const activeUploadLabelRef = useRef(null)
  const cameraVideoRef = useRef(null)
  const cameraStreamRef = useRef(null)
  const cameraSnapshotUrlRef = useRef('')
  const cameraCaptureTokenRef = useRef(0)

  const [cameraTarget, setCameraTarget] = useState(null)
  const [cameraStatus, setCameraStatus] = useState('loading')
  const [cameraError, setCameraError] = useState('')
  const [cameraSnapshot, setCameraSnapshot] = useState(null)
  const [cameraSnapshotUrl, setCameraSnapshotUrl] = useState('')
  const [cameraRetry, setCameraRetry] = useState(0)

  const [view, setView] = useState('home')
  const [theme, setTheme] = useState(() => localStorage.getItem('fs-v13-theme') || 'scarlet')
  const [participantCount, setParticipantCount] = useState(3)
  const [participants, setParticipants] = useState(
    PARTICIPANT_LABELS.map((label) => ({
      id: label,
      fileName: '',
      file: null,
      previewUrl: '',
      individualTrackId: null,
      soloGenre: null,
      ready: false,
      feature: null,
      consented: false,
    })),
  )
  const [tracks, setTracks] = useState([])
  const [createStep, setCreateStep] = useState(1)
  const [ensembleSelection, setEnsembleSelection] = useState([])
  const [selectedGenre, setSelectedGenre] = useState('pop')
  const [currentTrackId, setCurrentTrackId] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [confirmSessionEnd, setConfirmSessionEnd] = useState(false)
  const [collabMode, setCollabMode] = useState('random')
  const [collabCode, setCollabCode] = useState('')
  const [collabNotice, setCollabNotice] = useState('')
  const [analysisStatus, setAnalysisStatus] = useState('')
  const [busyParticipant, setBusyParticipant] = useState('')
  const [uploadingParticipant, setUploadingParticipant] = useState('')

  const activeParticipants = useMemo(
    () => participants.slice(0, participantCount),
    [participants, participantCount],
  )

  const registeredParticipants = useMemo(
    () => activeParticipants.filter((participant) => participant.ready),
    [activeParticipants],
  )

  const soloReadyParticipants = useMemo(
    () => activeParticipants.filter(
      (participant) => participant.ready && participant.individualTrackId &&
        tracks.some((track) => track.id === participant.individualTrackId),
    ),
    [activeParticipants, tracks],
  )

  const listenTracks = useMemo(
    () => [...tracks].reverse(),
    [tracks],
  )

  const playingTrack = tracks.find((track) => track.id === currentTrackId)

  useEffect(() => {
    const nextIds = new Set(tracks.map((track) => track.id))
    for (const old of tracksForCleanupRef.current) {
      if (!nextIds.has(old.id) && old.audioUrl) URL.revokeObjectURL(old.audioUrl)
    }
    tracksForCleanupRef.current = tracks
  }, [tracks])

  useEffect(() => {
    localStorage.setItem('fs-v13-theme', theme)
  }, [theme])

  useEffect(() => {
    return () => {
      stopCameraStream()
      if (cameraSnapshotUrlRef.current) {
        URL.revokeObjectURL(cameraSnapshotUrlRef.current)
        cameraSnapshotUrlRef.current = ''
      }
      stopPlayback()
      tracksForCleanupRef.current.forEach(track => { if(track.audioUrl) URL.revokeObjectURL(track.audioUrl) })
      participants.forEach((participant) => {
        if (participant.previewUrl) {
          URL.revokeObjectURL(participant.previewUrl)
        }
      })
    }
  }, [])

  // カメラ起動。閉じた場合や画面を離れた場合は映像を即座に停止する。
  useEffect(() => {
    if (cameraTarget === null) return

    let cancelled = false

    async function startCamera() {
      setCameraStatus('loading')
      setCameraError('')

      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        setCameraError('この環境ではカメラを起動できません。HTTPSまたはlocalhostで開いてください。')
        setCameraStatus('error')
        return
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
        })

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        cameraStreamRef.current = stream
        const video = cameraVideoRef.current
        if (!video) {
          stream.getTracks().forEach((track) => track.stop())
          cameraStreamRef.current = null
          return
        }

        video.srcObject = stream
        await video.play()
        if (!cancelled) setCameraStatus('ready')
      } catch (error) {
        if (cancelled) return
        if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError') {
          setCameraError('カメラの使用が許可されていません。ブラウザのカメラ権限を確認してください。')
        } else if (error?.name === 'NotFoundError') {
          setCameraError('使用できるカメラが見つかりません。')
        } else if (error?.name === 'NotReadableError') {
          setCameraError('カメラが他のアプリで使用中の可能性があります。')
        } else {
          setCameraError('カメラを起動できませんでした。画像アップロードをお試しください。')
        }
        setCameraStatus('error')
        stopCameraStream()
      }
    }

    startCamera()
    return () => {
      cancelled = true
      stopCameraStream()
    }
  }, [cameraTarget, cameraRetry])

  // カメラ画面でEscを押したら閉じる
  useEffect(() => {
    if (!cameraTarget) return
    const handleEscape = (event) => {
      if (event.key === 'Escape') closeCamera()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [cameraTarget])

  function stopCameraStream() {
    if (cameraStreamRef.current) {
      cameraStreamRef.current.getTracks().forEach((track) => track.stop())
      cameraStreamRef.current = null
    }
    if (cameraVideoRef.current) {
      cameraVideoRef.current.srcObject = null
    }
  }

  function clearSnapshot() {
    if (cameraSnapshotUrlRef.current) {
      URL.revokeObjectURL(cameraSnapshotUrlRef.current)
      cameraSnapshotUrlRef.current = ''
    }
    setCameraSnapshot(null)
    setCameraSnapshotUrl('')
  }

  function openCamera(label) {
    if (!participants.find(p => p.id === label)?.consented) {setErrorMessage('指紋画像の利用に同意してください。');return}
    cameraCaptureTokenRef.current += 1
    clearSnapshot()
    setCameraError('')
    setCameraStatus('loading')
    setCameraTarget(label)
  }

  function closeCamera() {
    cameraCaptureTokenRef.current += 1
    stopCameraStream()
    clearSnapshot()
    setCameraTarget(null)
    setCameraError('')
  }

  function retryCamera() {
    cameraCaptureTokenRef.current += 1
    stopCameraStream()
    clearSnapshot()
    setCameraError('')
    setCameraStatus('loading')
    setCameraRetry((previous) => previous + 1)
  }

  function takePhoto() {
    if (cameraStatus !== 'ready') return
    const video = cameraVideoRef.current
    if (!video || video.readyState < 2 || !video.videoWidth || !video.videoHeight) {
      setCameraError('映像の準備ができていません。しばらくしてから撮影してください。')
      return
    }

    // 撮影ガイドの中央付近を正方形に切り抜く
    const side = Math.floor(Math.min(video.videoWidth, video.videoHeight) * 0.7)
    const sx = Math.floor((video.videoWidth - side) / 2)
    const sy = Math.floor((video.videoHeight - side) / 2)
    const canvas = document.createElement('canvas')
    canvas.width = 900
    canvas.height = 900
    const context = canvas.getContext('2d')
    if (!context) {
      setCameraError('画像の処理に失敗しました。')
      return
    }
    context.drawImage(video, sx, sy, side, side, 0, 0, canvas.width, canvas.height)
    setCameraStatus('capturing')

    const captureToken = cameraCaptureTokenRef.current
    canvas.toBlob((blob) => {
      // 撮影中に閉じた場合、古い結果を破棄
      if (captureToken !== cameraCaptureTokenRef.current) return
      if (!blob) {
        setCameraError('画像を保存できませんでした。もう一度撮影してください。')
        setCameraStatus('ready')
        return
      }
      const file = new File([blob], `fingerprint_${cameraTarget}_${Date.now()}.jpg`, {
        type: 'image/jpeg',
      })
      clearSnapshot()
      const previewUrl = URL.createObjectURL(file)
      cameraSnapshotUrlRef.current = previewUrl
      setCameraSnapshot(file)
      setCameraSnapshotUrl(previewUrl)
      setCameraStatus('captured')
      stopCameraStream()
    }, 'image/jpeg', 0.92)
  }

  function confirmCapturedPhoto() {
    if (!cameraSnapshot || !cameraTarget) return
    registerParticipantFile(cameraSnapshot, cameraTarget)
    closeCamera()
  }

  function uploadInstead() {
    const label = cameraTarget
    closeCamera()
    if (label) openFileDialog(label)
  }

  function openCollabMode(mode) {
    setCollabMode(mode)
    setCollabCode('')
    setCollabNotice('')
    setErrorMessage('')
    setView('collab')
  }

  function resetCreateFlow(nextCount = participantCount) {
    setParticipantCount(nextCount)
    setCreateStep(1)
    setEnsembleSelection([])
    setSelectedGenre('pop')
    setErrorMessage('')
    setView('create')
  }

  function stopPlayback() {
    if (playbackTimerRef.current) { clearTimeout(playbackTimerRef.current); playbackTimerRef.current = null }
    if (audioElementRef.current) {
      audioElementRef.current.pause()
      audioElementRef.current.src = ''
      audioElementRef.current = null
    }
    if (audioContextRef.current) {audioContextRef.current.close().catch(()=>{});audioContextRef.current = null}
    setCurrentTrackId('')
  }

  async function playTrack(track) {
    if (currentTrackId === track.id) {stopPlayback();return}
    stopPlayback()
    try {
      if (!track.audioUrl) throw Error('音源がありません。')
      const audio = new Audio(track.audioUrl)
      audioElementRef.current = audio
      audio.onended = () => {if(audioElementRef.current === audio) stopPlayback()}
      audio.onerror = () => {if(audioElementRef.current === audio) {stopPlayback();setErrorMessage('音源を再生できませんでした。')}}
      await audio.play()
      setCurrentTrackId(track.id)
      setErrorMessage('')
    } catch(error) {stopPlayback();setErrorMessage('音楽の再生に失敗しました。')}
  }

  function openFileDialog(label) {
    if (!participants.find(p => p.id === label)?.consented) {setErrorMessage('指紋画像の利用に同意してください。');return}
    if (uploadingParticipant) return
    activeUploadLabelRef.current = label
    hiddenFileInputRef.current?.click()
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !activeUploadLabelRef.current) return
    registerParticipantFile(file, activeUploadLabelRef.current)
  }

  // 画像ファイルをバックエンドで一時検証し、成功後にブラウザ内で登録する。
  // 指紋解析と作曲は引き続きこの端末内で実行する。
  async function registerParticipantFile(file, targetLabel) {
    if (!participants.find(p => p.id === targetLabel)?.consented) {
      setErrorMessage('指紋画像の利用に同意してください。')
      return
    }
    if (uploadingParticipant) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setErrorMessage('JPEG・PNG・WebPの画像を選択してください。')
      return
    }
    if (!file.size || file.size > 10 * 1024 * 1024) {
      setErrorMessage('画像は10MB以下にしてください。')
      return
    }

    const uploadToken = ++uploadTokenRef.current[targetLabel]
    setUploadingParticipant(targetLabel)
    setErrorMessage('')
    try {
      await validateImageWithBackend(file, targetLabel)
      // 送信中に削除・同意撤回された場合は結果を取り込まない。
      if (uploadToken !== uploadTokenRef.current[targetLabel]) return

      generationTokenRef.current[targetLabel] += 1
      setBusyParticipant('')
      setAnalysisStatus('')
      stopPlayback()
      const previewUrl = URL.createObjectURL(file)

      setParticipants((previous) => previous.map((participant) => {
        if (participant.id !== targetLabel) return participant
        if (participant.previewUrl) URL.revokeObjectURL(participant.previewUrl)
        return {
          ...participant,
          fileName: file.name,
          file,
          previewUrl,
          individualTrackId: null,
          soloGenre: null,
          ready: true,
          feature: null,
          consented: true,
        }
      }))
      // 指紋画像が変わった場合は古い曲を無効化する。
      setTracks((previous) => previous.filter((track) => !track.participants.includes(targetLabel)))
      setEnsembleSelection((previous) => previous.filter((id) => id !== targetLabel))
    } catch (error) {
      if (uploadToken === uploadTokenRef.current[targetLabel]) {
        setErrorMessage(`参加者${targetLabel}の画像登録：${error.message}`)
      }
    } finally {
      if (uploadToken === uploadTokenRef.current[targetLabel]) setUploadingParticipant('')
    }
  }

  // 画像を端末内のWeb Workerで解析し、指紋分類によってジャンルを自動決定する。
  async function generateSoloTrack(label) {
    const participant = participants.find((item) => item.id === label)
    if (!participant?.ready || !participant.file || !participant.consented) {
      setErrorMessage(`参加者${label}の指紋画像を登録してください。`)
      return
    }
    if (busyParticipant || uploadingParticipant) return
    const token = ++generationTokenRef.current[label]
    stopPlayback()
    setBusyParticipant(label)
    setAnalysisStatus('画像を解析しています…')
    setErrorMessage('')
    try {
      const observed = await analyzeFingerprint(participant.file, setAnalysisStatus, participant.cropRatio ?? 1)
      // Missing measurements remain explicitly marked; 32 is only an audio tempo setting.
      const missingRidges = observed.ridgeCount == null
      const feature = missingRidges ? {
        ...observed,
        ridgeCount: 32,
        analysis: {
          ...observed.analysis,
          approximate: true,
          ridgeStatus: 'unavailable',
          warning: `${observed.analysis?.warning || ''} 隆線交差数は取得できなかったため、音楽用の仮設定32（80 BPM）で作曲しました。これは測定結果ではありません。`,
        },
      } : observed
      if (!missingRidges && (observed.ridgeCount < 32 || observed.ridgeCount > 64)) {
        feature.analysis = {...feature.analysis,
          warning: `${feature.analysis?.warning || ''} テンポは再生しやすい80〜160 BPMに調整します。表示した隆線交差数は変更しません。`,
        }
      }
      if (token !== generationTokenRef.current[label]) return
      setAnalysisStatus('解析完了。個人曲の音源を作成しています…')
      // Let the browser paint the status before synchronous audio rendering.
      await new Promise(resolve => setTimeout(resolve, 50))
      if (token !== generationTokenRef.current[label]) return
      const nextTrack = buildTrack([{id: label, feature}], 'individual')
      setParticipants(previous => previous.map(item => item.id === label ? {
        ...item, feature, soloGenre: PATTERN_GENRE[feature.candidate], individualTrackId:nextTrack.id,
      }:item))
      setTracks(previous => [...previous.filter(track => !track.participants.includes(label)),nextTrack])
      setEnsembleSelection(previous=> previous.filter(id=>id !== label))
    } catch (error) {
      if(token === generationTokenRef.current[label]) setErrorMessage(`参加者${label}：${error.message}`)
    } finally {
      if(token === generationTokenRef.current[label]) {setBusyParticipant('');setAnalysisStatus('')}
    }
  }

  function removeParticipant(label) {
    uploadTokenRef.current[label] += 1
    setUploadingParticipant((current) => current === label ? '' : current)
    generationTokenRef.current[label] += 1
    setBusyParticipant('')
    setAnalysisStatus('')
    stopPlayback()
    setParticipants((previous) =>
      previous.map((participant) => {
        if (participant.id !== label) return participant
        if (participant.previewUrl) {
          URL.revokeObjectURL(participant.previewUrl)
        }
        return {
          ...participant,
          fileName: '',
          file: null,
          previewUrl: '',
          individualTrackId: null,
          soloGenre: null,
          ready: false,
          feature: null,
          consented: false,
        }
      }),
    )
    setTracks((previous) => previous.filter((track) => !track.participants.includes(label)))
    setEnsembleSelection((previous) => previous.filter((id) => id !== label))
  }

  function toggleSelection(label) {
    if (!soloReadyParticipants.find((participant) => participant.id === label)) return

    setEnsembleSelection((previous) => {
      if (previous.includes(label)) {
        return previous.filter((id) => id !== label)
      }
      if (previous.length >= 3) return previous
      return [...previous, label]
    })
  }

  function generateEnsembleTrack() {
    const selected = ensembleSelection.map(id => participants.find(p=>p.id===id))
    if (selected.length < 2 || selected.some(p=>!p?.feature || !p.individualTrackId)) {
      setErrorMessage('個人曲を生成済みの参加者を2人以上選択してください。')
      return
    }
    try {
      stopPlayback()
      const nextTrack = buildTrack(selected.map(p=>({id:p.id,feature:p.feature})), 'ensemble')
      const key = [...ensembleSelection].sort().join('|')
      setTracks(previous => [...previous.filter(track=> track.type !== 'ensemble' || [...track.participants].sort().join('|') !== key), nextTrack])
      setView('listen')
      setErrorMessage('')
    } catch(error){setErrorMessage(`共同曲の生成に失敗しました：${error.message}`)}
  }

  function clearSession() {
    for(const label of PARTICIPANT_LABELS) {
      generationTokenRef.current[label] += 1
      uploadTokenRef.current[label] += 1
    }
    setUploadingParticipant('')
    setBusyParticipant('')
    setAnalysisStatus('')
    closeCamera()
    stopPlayback()
    participants.forEach((participant) => {
      if (participant.previewUrl) {
        URL.revokeObjectURL(participant.previewUrl)
      }
    })
    setParticipants(
      PARTICIPANT_LABELS.map((label) => ({
        id: label,
        fileName: '',
        file: null,
        previewUrl: '',
        individualTrackId: null,
        soloGenre: null,
        ready: false,
        feature: null,
        consented: false,
      })),
    )
    setTracks([])
    setParticipantCount(3)
    setCreateStep(1)
    setEnsembleSelection([])
    setSelectedGenre('pop')
    setErrorMessage('')
    setConfirmSessionEnd(false)
    setView('home')
  }

  function themeClass() {
    return `theme-${theme}`
  }

  return (
    <div className={`app-shell ${themeClass()}`}>
      <input
        ref={hiddenFileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden-input"
        onChange={handleFileChange}
      />

      <header className="topbar">
        <button className="brand-button" onClick={() => setView('home')}>
          <span className="brand-mark">FS</span>
          <span className="brand-copy">
            <strong>Fingerprint</strong>
            <span>Symphony</span>
          </span>
        </button>

        <nav className="top-nav">
          <button className={`top-nav-item ${view === 'create' ? 'active' : ''}`} onClick={() => resetCreateFlow()}>
            この端末で作る
          </button>
          <button className={`top-nav-item ${view === 'listen' ? 'active' : ''}`} onClick={() => setView('listen')}>
            聴く
          </button>
          <button className={`top-nav-item ${view === 'settings' ? 'active' : ''}`} onClick={() => setView('settings')}>
            設定
          </button>
        </nav>
      </header>

      <main className={`main-stage ${playingTrack ? 'has-playing-track' : ''}`}>
        {errorMessage && <div className="global-error">{errorMessage}</div>}
        {analysisStatus && <div className="global-error" role="status">{analysisStatus}</div>}
        {uploadingParticipant && <div className="global-error" role="status">参加者{uploadingParticipant}の画像をサーバーで確認しています…</div>}

        {view === 'home' && (
          <section className="home-view">
            <div className="hero-copy-block">
              <div className="eyebrow-tag">MUSIC x FINGERPRINT EXPERIENCE</div>
              <div className="hero-orbit" aria-hidden="true">
                <span className="hero-orbit-ring ring-a" />
                <span className="hero-orbit-ring ring-b" />
                <span className="hero-orbit-core"><FingerprintIcon /></span>
                <span className="orbit-tag orbit-tag-a">UNIQUE SIGNAL</span>
                <span className="orbit-tag orbit-tag-b">LIVE 01:01</span>
              </div>
              <span className="hero-issue">VOL.01 — ORIGINAL CONNECTION ENGINE</span>
              <h1 className="hero-title">
                MAKE<br />
                <span>YOUR SOUND.</span>
              </h1>
              <p className="hero-text">
                あなたの指紋から個人曲を作り、<br />
                出会った誰かと新しい共同曲を生み出す。
              </p>
              <div className="hero-cta-note"><span className="live-dot" /> READY TO MAKE NOISE</div>
            </div>

            <div className="command-grid" aria-label="作曲方法を選択">
              <div className="mode-heading">
                <span className="mode-heading-kicker">SELECT YOUR MODE</span>
                <span className="mode-heading-title">どうやって音楽を作る？</span>
              </div>

              <button type="button" className="command-card create" onClick={() => resetCreateFlow()}>
                <span className="command-index">01 / LOCAL CREATE</span>
                <span className="command-glyph" aria-hidden="true">▣</span>
                <span className="command-main">この端末で作る</span>
                <span className="command-sub">1台の端末で1〜3人の音楽を作る</span>
                <span className="command-arrow" aria-hidden="true">↗</span>
              </button>

              <button type="button" className="command-card friends" onClick={() => openCollabMode('friends')}>
                <span className="command-index">02 / FRIENDS ROOM</span>
                <span className="command-glyph" aria-hidden="true">♧</span>
                <span className="command-main">友達と作る</span>
                <span className="command-sub">招待コードで離れた友達とも共同作曲</span>
                <span className="command-arrow" aria-hidden="true">↗</span>
              </button>

              <button type="button" className="command-card random" onClick={() => openCollabMode('random')}>
                <span className="command-index">03 / RANDOM MATCH</span>
                <span className="command-glyph" aria-hidden="true">◎</span>
                <span className="command-main">ランダムで作る</span>
                <span className="command-sub">知らない誰かと新しい音楽を作る</span>
                <span className="command-arrow" aria-hidden="true">↗</span>
              </button>
            </div>

            <section className="community-panel" aria-label="ライブラリと設定">
              <div className="community-title-row">
                <span className="community-kicker">MY MUSIC / CONTROL</span>
                <span className="community-heading">聴く・設定</span>
              </div>
              <div className="community-actions">
                <button type="button" className="community-action listen-shortcut" onClick={() => setView('listen')}>
                  <span className="community-icon" aria-hidden="true">♫</span>
                  <span className="community-copy"><strong>聴く</strong><small>YOUR LIBRARY</small></span>
                  <span className="community-arrow" aria-hidden="true">↗</span>
                </button>
                <button type="button" className="community-action settings-shortcut" onClick={() => setView('settings')}>
                  <span className="community-icon" aria-hidden="true">⚙</span>
                  <span className="community-copy"><strong>設定</strong><small>THEME &amp; SESSION</small></span>
                  <span className="community-arrow" aria-hidden="true">↗</span>
                </button>
              </div>
            </section>

            <section className="home-side-panel">
              <div className="side-kicker">SESSION STATUS</div>
              <span className="side-ornament" aria-hidden="true">///</span>
              <div className="mini-stat-grid">
                <div className="mini-stat">
                  <span className="mini-stat-number">{tracks.length}</span>
                  <span className="mini-stat-label">TRACKS</span>
                </div>
                <div className="mini-stat">
                  <span className="mini-stat-number">{registeredParticipants.length}</span>
                  <span className="mini-stat-label">PLAYERS</span>
                </div>
                <div className="mini-stat">
                  <span className="mini-stat-number">{participantCount}</span>
                  <span className="mini-stat-label">TARGET</span>
                </div>
              </div>
            </section>
            <div className="home-ticker" aria-hidden="true">
              <div className="ticker-motion">FINGERPRINT  ✦  SOUND  ✦  CONNECTION  ✦  FINGERPRINT  ✦  SOUND  ✦  CONNECTION  ✦</div>
            </div>
          </section>
        )}

        {view === 'collab' && (
          <section className="collab-view panel-frame">
            <div className="panel-header collab-header">
              <span className="panel-label">CONNECT MODE</span>
              <h2>あなたの音と、誰かの音。</h2>
              <p>離れた友達と作るか、知らない誰かと作るかを選べます。</p>
            </div>
            <div className="collab-mode-switch" role="group" aria-label="コラボ方法">
              <button type="button" className={collabMode === 'friends' ? 'active' : ''} onClick={() => openCollabMode('friends')}>友達と作る</button>
              <button type="button" className={collabMode === 'random' ? 'active' : ''} onClick={() => openCollabMode('random')}>ランダムで作る</button>
            </div>

            <div className="collab-intro">
              <span className="collab-number">{collabMode === 'friends' ? '02 / FRIENDS ROOM' : '03 / RANDOM MATCH'}</span>
              <h3>{collabMode === 'friends' ? '離れた友達とも、ひとつの曲を。' : '知らない誰かと、思いがけない曲を。'}</h3>
              <p>{collabMode === 'friends'
                ? '招待コードを共有して参加する方式です。同じ場所にいなくても参加できる想定です。'
                : 'ランダムに相手とつながり、互いに同意した音楽的特徴を使って共同曲を作る構想です。'}</p>
            </div>

            {collabMode === 'friends' ? (
              <div className="collab-room-grid">
                <article className="collab-choice-card">
                  <div className="choice-topline">CREATE INVITE ROOM</div>
                  <div className="choice-icon">✳</div>
                  <h4>招待ルームを作る</h4>
                  <p>招待コードを友達に送って、別々の端末から同じルームに参加します。離れていても使える想定です。</p>
                  <button type="button" className="action-button" onClick={() => setCollabNotice('ルーム作成はまだ未実装です。Cloud Runのルーム管理API接続後に利用できます。')}>
                    ルームを作成
                  </button>
                </article>
                <article className="collab-choice-card">
                  <div className="choice-topline">JOIN WITH CODE</div>
                  <div className="choice-icon">#</div>
                  <h4>招待コードで参加</h4>
                  <p>友達から届いたコードを入力して参加する想定です。現在は入力画面のみ利用できます。</p>
                  <label className="collab-room-label" htmlFor="collab-room-code">招待コード</label>
                  <input id="collab-room-code" className="collab-room-input" placeholder="例：FS-4821" value={collabCode} maxLength={16} onChange={(event) => setCollabCode(event.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, ''))} />
                  <button type="button" className="ghost-button" disabled={!collabCode.trim()} onClick={() => setCollabNotice(`「${collabCode}」への参加は未実装です。Cloud Runの参加API接続後に利用できます。`)}>
                    コードで参加
                  </button>
                </article>
              </div>
            ) : (
              <div className="collab-room-grid">
                <article className="collab-choice-card">
                  <div className="choice-topline">RANDOM MATCHING</div>
                  <div className="choice-icon">◎</div>
                  <h4>新しい相手を探す</h4>
                  <p>知らない相手とマッチングして、その人の音楽的特徴と自分の音楽的特徴を組み合わせる構想です。</p>
                  <button type="button" className="action-button" onClick={() => setCollabNotice('ランダムマッチングはまだ未実装です。Cloud RunのマッチングAPI接続後に利用できます。')}>
                    マッチングを開始
                  </button>
                </article>
                <article className="collab-choice-card">
                  <div className="choice-topline">BEFORE YOU CONNECT</div>
                  <div className="choice-icon">♫</div>
                  <h4>自分の音を準備する</h4>
                  <p>マッチング前に指紋を登録して個人曲を作る想定です。相手に指紋画像そのものを公開しない設計にします。</p>
                  <button type="button" className="ghost-button" onClick={() => resetCreateFlow(1)}>
                    個人曲を作る
                  </button>
                </article>
              </div>
            )}

            {collabNotice && <div className="collab-notice" role="status">{collabNotice}</div>}
            <div className="collab-disclaimer">
              <span className="collab-demo-label">PROTOTYPE / API NOT CONNECTED</span>
              <p>現在、コラボ画面の選択と招待コード入力だけが動作します。異なる端末との接続・ルーム発行・ランダムマッチングは未実装です。実装時には指紋画像を他者へ共有せず、同意を得た音楽情報だけを使う方針です。</p>
            </div>
            <div className="footer-actions collab-footer-actions">
              <button type="button" className="ghost-button" onClick={() => setView('home')}>ホームに戻る</button>
              <button type="button" className="action-button" onClick={() => resetCreateFlow(1)}>この端末で個人曲を作る</button>
            </div>
          </section>
        )}

        {view === 'create' && (
          <section className="create-view panel-frame">
            <div className="panel-header">
              <span className="panel-label">LOCAL CREATE / ONE DEVICE</span>
              <h2>個人曲から共同曲へ</h2>
              <p>この端末を順番に使うモードです。人数選択 → 指紋登録・個人曲生成 → 共同曲生成</p>
            </div>

            <div className="step-tabs">
              {[1, 2, 3].map((step) => (
                <button
                  key={step}
                  className={`step-tab ${createStep === step ? 'active' : ''}`}
                  onClick={() => setCreateStep(step)}
                  disabled={step === 3 && soloReadyParticipants.length !== participantCount}
                  title={step === 3 && soloReadyParticipants.length !== participantCount ? '先に全員の個人曲を生成してください' : undefined}
                >
                  STEP {step}
                </button>
              ))}
            </div>

            {createStep === 1 && (
              <div className="step-panel">
                <div className="panel-burst">STEP 1</div>
                <h3>何人で音楽を作る？</h3>
                <div className="count-grid">
                  {[1, 2, 3].map((count) => (
                    <button
                      key={count}
                      className={`count-card ${participantCount === count ? 'active' : ''}`}
                      onClick={() => {
                        setParticipantCount(count)
                        setEnsembleSelection((previous) => previous.filter((id) => PARTICIPANT_LABELS.slice(0, count).includes(id)))
                      }}
                    >
                      <span className="count-number">{count}</span>
                      <span className="count-label">MEMBERS</span>
                    </button>
                  ))}
                </div>
                <button className="action-button" onClick={() => setCreateStep(2)}>
                  指紋登録へ進む
                </button>
              </div>
            )}

            {createStep === 2 && (
              <div className="step-panel">
                <div className="panel-burst">STEP 2</div>
                <h3>指紋登録と個人曲の生成</h3>
                <p className="camera-instruction-lead">各参加者の指紋を撮影・アップロードした後、「個人曲を生成」を押してください。画像はサーバーで一時的に形式確認し、指紋の解析と作曲は端末内で実行します。</p>
                <div className="solo-progress" role="status">
                  <span>個人曲の生成状況</span>
                  <strong>{soloReadyParticipants.length} / {participantCount} 完了</strong>
                </div>
                <div className="participant-grid">
                  {activeParticipants.map((participant) => {
                    const soloTrack = tracks.find((track) => track.id === participant.individualTrackId)
                    return (
                      <article key={participant.id} className={`participant-card ${participant.ready ? 'ready' : ''}`}>
                        <div className="participant-card-top">
                          <span className="participant-chip">PLAYER {participant.id}</span>
                          <span className={`status-chip ${soloTrack ? '' : 'pending'}`}>
                            {uploadingParticipant === participant.id ? '画像確認中' : soloTrack ? '個人曲完成' : busyParticipant === participant.id ? '指紋解析中' : participant.ready ? '解析待ち' : '未登録'}
                          </span>
                        </div>

                        <div className="participant-preview">
                          {participant.previewUrl ? (
                            <img src={participant.previewUrl} alt={`Participant ${participant.id}`} className="participant-image" />
                          ) : (
                            <div className="participant-placeholder">
                              <FingerprintIcon />
                            </div>
                          )}
                        </div>

                        <div className="participant-info">
                          <div className="participant-name">PARTICIPANT {participant.id}</div>
                          <div className="participant-file">{participant.fileName || '指紋画像をまだ登録していません'}</div>
                        </div>

                        <label className="fingerprint-consent">
                          <input type="checkbox" checked={participant.consented} onChange={(event) => {
                            const consent = event.target.checked
                            if(!consent) {
                              uploadTokenRef.current[participant.id] += 1
                              setUploadingParticipant((current) => current === participant.id ? '' : current)
                            }
                            if(!consent && participant.ready) removeParticipant(participant.id)
                            else setParticipants(previous=>previous.map(p=>p.id===participant.id?{...p,consented:consent}:p))
                          }} />
                          <span>本人の指紋画像を一時的にサーバーへ送信して形式を確認し、端末内で解析・作曲に利用することに同意する（サーバーへの永続保存なし、端末内のデータは削除操作・終了時に破棄）</span>
                        </label>
                        <div className="participant-actions camera-participant-actions">
                          <button className="action-button compact camera-launch-button" onClick={() => openCamera(participant.id)} disabled={!participant.consented || Boolean(uploadingParticipant)}>
                            <span aria-hidden="true">◉</span> カメラで撮影
                          </button>
                          <button className="ghost-button compact" onClick={() => openFileDialog(participant.id)} disabled={!participant.consented || Boolean(uploadingParticipant)}>
                            画像をアップロード
                          </button>
                          <button className="ghost-button compact participant-delete-button" onClick={() => removeParticipant(participant.id)} disabled={!participant.ready}>
                            完全削除
                          </button>
                        </div>

                        {participant.ready && (
                          <div className="solo-genre-panel">
                            <div className="solo-genre-heading">
                              <span>FINGERPRINT GENRE</span>
                              <strong>{participant.feature ? `${participant.soloGenre}（参考推定）` : '指紋分類から自動で決定'}</strong>
                            </div>
                            {busyParticipant === participant.id && (
                              <div className="solo-generation-status" role="status" aria-live="polite">
                                <strong>個人曲を作成中…</strong>
                                <span>{analysisStatus || '指紋画像を解析しています…'}</span>
                                <span>完了すると、この下に再生ボタンが表示されます。</span>
                              </div>
                            )}
                            {errorMessage.startsWith(`参加者${participant.id}：`) && (
                              <p className="solo-generation-error" role="alert">{errorMessage}</p>
                            )}
                            {!soloTrack && (
                              <label className="solo-crop-control">
                                解析する範囲
                                <select value={participant.cropRatio ?? 1} disabled={Boolean(busyParticipant || uploadingParticipant)}
                                  onChange={event => {
                                    const cropRatio = Number(event.target.value)
                                    setParticipants(previous => previous.map(p => p.id === participant.id ? {...p, cropRatio} : p))
                                    setErrorMessage('')
                                  }}>
                                  <option value={1}>写真全体（指腹を切り出し済み）</option>
                                  <option value={0.7}>中央70%（背景を除く）</option>
                                  <option value={0.5}>中央50%（指腹を拡大）</option>
                                </select>
                                <span>指腹が写真の中央にある場合に選択し、もう一度生成してください。線の中心と周囲の曲がりを含めてください。</span>
                              </label>
                            )}
                            {soloTrack ? (
                              <div>
                                <p className="solo-genre-hint ready">指紋の種類候補：{participant.feature.candidate} / 隆線交差数の目安：{participant.feature.analysis?.ridgeStatus === 'unavailable' ? '未取得（音楽用の仮設定32／80 BPM）' : participant.feature.ridgeCount} / 特徴点候補：{participant.feature.minutiae.length}件（参考推定）</p>
                                {participant.feature.analysis?.warning && (
                                  <div className="solo-estimate-notice" role="status">
                                    <strong>{participant.feature.analysis.approximate ? '読み取れた範囲で曲を作成しました' : '解析結果について'}</strong>
                                    <p>{participant.feature.analysis.warning}</p>
                                  </div>
                                )}
                              </div>
                            ) : (
                              <button type="button" className="action-button solo-generate-button"
                                disabled={Boolean(busyParticipant || uploadingParticipant)} onClick={() => generateSoloTrack(participant.id)}>
                                {busyParticipant === participant.id ? '解析中…' : '♪ 指紋から個人曲を生成'}
                              </button>
                            )}
                          </div>
                        )}

                        <div className="participant-track-line">
                          <span>個人曲</span>
                          <strong>{soloTrack ? `✓ 完成：${soloTrack.title}（${soloTrack.genre.toUpperCase()}）` : busyParticipant === participant.id ? '作成中…' : '未生成'}</strong>
                          {soloTrack && (
                            <button className="inline-play" onClick={() => playTrack(soloTrack)}>
                              {currentTrackId === soloTrack.id ? '■ 停止' : '▶ 個人曲を聴く'}
                            </button>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </div>

                <div className="footer-actions">
                  <button className="ghost-button" onClick={() => setCreateStep(1)}>
                    戻る
                  </button>
                  <button
                    className="action-button"
                    onClick={() => setCreateStep(3)}
                    disabled={soloReadyParticipants.length !== participantCount || Boolean(uploadingParticipant)}
                  >
                    次へ進む
                  </button>
                </div>
              </div>
            )}

            {createStep === 3 && (
              <div className="step-panel">
                <div className="panel-burst">STEP 3</div>
                <h3>共同曲を生成する</h3>

                {participantCount === 1 ? (
                  <div className="solo-message-box">
                    <p>1人モードでは、指紋から生成した個人曲を「聴く」から再生できます。</p>
                    <button className="action-button" onClick={() => setView('listen')}>
                      「聴く」で個人曲を確認する
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="selection-block">
                      <span className="block-title">参加者を選択</span>
                      <div className="selection-row">
                        {soloReadyParticipants.map((participant) => (
                          <button
                            key={participant.id}
                            className={`selection-tag ${ensembleSelection.includes(participant.id) ? 'active' : ''}`}
                            onClick={() => toggleSelection(participant.id)}
                          >
                            {participant.id}
                          </button>
                        ))}
                      </div>
                      <p className="hint-text">A+BからA+Cに切り替えても、データは削除されません。</p>
                    </div>

                    <div className="selection-block">
                      <span className="block-title">共同曲のジャンル</span>
                      <p className="hint-text">先頭に選択した参加者の指紋の種類で自動決定します（Arch＝ヒップホップ / Loop＝ハウス / Whorl＝テクノ）。</p>
                    </div>

                    <div className="ensemble-summary">
                      <div>
                        <span className="summary-label">SELECTED</span>
                        <strong>{ensembleSelection.length ? ensembleSelection.join(' + ') : '未選択'}</strong>
                      </div>
                      <div>
                        <span className="summary-label">GENRE</span>
                        <strong>{ensembleSelection.length && participants.find(p=>p.id===ensembleSelection[0])?.soloGenre || '自動判定'}</strong>
                      </div>
                    </div>

                    <div className="footer-actions">
                      <button className="ghost-button" onClick={() => setCreateStep(2)}>
                        戻る
                      </button>
                      <button className="action-button" onClick={generateEnsembleTrack}>
                        共同曲を生成する
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}
          </section>
        )}

        {view === 'listen' && (
          <section className="listen-view panel-frame">
            <div className="panel-header">
              <span className="panel-label">LISTEN MODE</span>
              <h2>セッション内の楽曲</h2>
              <p>個人曲と共同曲をいつでも再生できます</p>
            </div>

            {listenTracks.length === 0 ? (
              <div className="empty-box">まだ曲がありません。「作る」から個人曲や共同曲を生成してね。</div>
            ) : (
              <div className="track-grid">
                {listenTracks.map((track) => (
                  <article key={track.id} className={`track-card ${currentTrackId === track.id ? 'playing' : ''}`}>
                    <div className="track-art" aria-hidden="true">
                      <div className="track-art-disc"><FingerprintIcon /></div>
                      <span>{track.accent}</span>
                      <span className="track-art-no">FS / {track.participants.join('')}</span>
                    </div>
                    <div className="track-body">
                      <div className="track-kind">{track.type === 'individual' ? 'INDIVIDUAL' : 'ENSEMBLE'}</div>
                      <h3>{track.title}</h3>
                      <p>{track.subtitle}</p>
                      <div className="track-meta">{track.participants.join(' + ')} {track.genre ? ` / ${track.genre.toUpperCase()}` : ''}</div>
                      <div className={`track-wave ${currentTrackId === track.id ? 'active' : ''}`} aria-hidden="true">
                        {Array.from({ length: 22 }, (_, index) => (
                          <i key={index} style={{ '--wave-index': index }} />
                        ))}
                      </div>
                    </div>
                    <button className="play-plate" onClick={() => playTrack(track)}>
                      {currentTrackId === track.id ? 'STOP' : 'PLAY'}
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {view === 'settings' && (
          <section className="settings-view panel-frame">
            <div className="panel-header">
              <span className="panel-label">SETTINGS</span>
              <h2>テーマとセッション管理</h2>
              <p>サイトカラーの切替とセッションの初期化</p>
              <p className="demo-caption">端末内で指紋画像を参考解析して曲を生成します。実写真での認識精度は未検証です。画像・特徴量はサーバーへ送信しません。</p>
            </div>

            <div className="settings-block">
              <h3>COLOR THEME / 8 COLORS</h3>
              <div className="theme-card-grid">
                {THEMES.map((item) => (
                  <button
                    key={item.id}
                    className={`theme-card ${theme === item.id ? 'active' : ''}`}
                    onClick={() => setTheme(item.id)}
                  >
                    <span className={`theme-swatch ${item.id}`} />
                    <strong>{item.name}</strong><small className="theme-detail">{item.detail}</small>
                  </button>
                ))}
              </div>
            </div>

            <div className="settings-block session-box">
              <div className="session-warning-heading">
                <span className="session-warning-icon" aria-hidden="true">!</span>
                <div>
                  <span className="session-overline">DANGER ZONE / SESSION</span>
                  <h3>セッションを終了</h3>
                </div>
              </div>
              <p className="session-warning-description">
                現在の参加者情報と個人曲・共同曲をすべて削除します。
                この操作は取り消せません。
              </p>
              <div className="session-summary-line">
                <span>登録済み参加者：<strong>{registeredParticipants.length}人</strong></span>
                <span>生成済み楽曲：<strong>{tracks.length}曲</strong></span>
              </div>
              {!confirmSessionEnd ? (
                <button
                  className="danger-button session-end-button"
                  type="button"
                  onClick={() => setConfirmSessionEnd(true)}
                >
                  <span aria-hidden="true">×</span> セッションを終了する
                </button>
              ) : (
                <div className="session-confirm-box" role="region" aria-live="polite" aria-labelledby="session-confirm-title" aria-describedby="session-confirm-desc">
                  <strong id="session-confirm-title">本当にすべて削除しますか？</strong>
                  <p id="session-confirm-desc">指紋画像・参加者情報・セッション内の楽曲が削除されます。</p>
                  <div className="session-confirm-actions">
                    <button type="button" className="ghost-button session-cancel-button" onClick={() => setConfirmSessionEnd(false)}>
                      キャンセル
                    </button>
                    <button type="button" className="danger-button session-delete-confirm" onClick={clearSession}>
                      すべて削除して終了
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>
        )}
      </main>

      {cameraTarget && (
        <div className="camera-overlay">
          <section
            className="camera-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="camera-dialog-title"
          >
            <div className="camera-dialog-header">
              <div>
                <span className="camera-overline">LIVE CAMERA / PLAYER {cameraTarget}</span>
                <h2 id="camera-dialog-title">指紋を撮影</h2>
              </div>
              <button className="camera-close" type="button" onClick={closeCamera} aria-label="カメラを閉じる">
                ×
              </button>
            </div>

            <div className="camera-viewfinder">
              {cameraStatus !== 'captured' && (
                <video
                  ref={cameraVideoRef}
                  autoPlay
                  muted
                  playsInline
                  className="camera-video"
                  aria-label="カメラ映像"
                />
              )}
              {cameraStatus === 'captured' && cameraSnapshotUrl && (
                <img className="camera-captured-image" src={cameraSnapshotUrl} alt="撮影した指紋画像" />
              )}

              {(cameraStatus === 'ready' || cameraStatus === 'loading' || cameraStatus === 'capturing') && (
                <div className="camera-overlay-guide" aria-hidden="true">
                  <div className="camera-guide-frame">
                    <span className="guide-corner corner-tl" />
                    <span className="guide-corner corner-tr" />
                    <span className="guide-corner corner-bl" />
                    <span className="guide-corner corner-br" />
                    <span className="camera-guide-text">枠の中心に指をかざしてください</span>
                    <span className="camera-guide-reticle">＋</span>
                  </div>
                </div>
              )}
              {cameraStatus === 'loading' && <div className="camera-busy">カメラを起動しています...</div>}
              {cameraStatus === 'capturing' && <div className="camera-busy">撮影画像を処理中...</div>}
              {cameraStatus === 'captured' && <span className="camera-preview-badge">撮影画像の確認</span>}
              {cameraStatus === 'error' && <div className="camera-error-screen">カメラを利用できません</div>}
            </div>

            {cameraError && <p className="camera-message-error" role="alert">{cameraError}</p>}
            <p className="camera-help">
              {cameraStatus === 'captured'
                ? '画像を確認し、問題なければ登録してください。'
                : '指紋の模様が見えるように、明るい場所でゆっくり撮影してください。'}
            </p>

            <div className="camera-controls">
              {cameraStatus === 'captured' ? (
                <>
                  <button className="ghost-button" type="button" onClick={retryCamera}>撮り直す</button>
                  <button className="action-button" type="button" onClick={confirmCapturedPhoto}>この画像を登録</button>
                </>
              ) : cameraStatus === 'error' ? (
                <>
                  <button className="ghost-button" type="button" onClick={retryCamera}>再試行</button>
                  <button className="action-button" type="button" onClick={uploadInstead}>画像をアップロード</button>
                </>
              ) : (
                <>
                  <button className="ghost-button" type="button" onClick={closeCamera}>キャンセル</button>
                  <button className="camera-shutter" type="button" onClick={takePhoto} disabled={cameraStatus !== 'ready'} aria-label="撮影する">
                    <span />
                  </button>
                  <span className="camera-shutter-spacer">撮影</span>
                </>
              )}
            </div>
            <div className="camera-privacy-note">撮影画像は「この画像を登録」を押した後、形式確認のためサーバーに一時送信されます。指紋解析と音楽生成は端末内で行います。</div>
          </section>
        </div>
      )}

      {playingTrack && (
        <aside className="mini-player" aria-label="再生中の楽曲">
          <div className="mini-player-art" aria-hidden="true">♪</div>
          <div className="mini-player-info">
            <strong>{playingTrack.title}</strong>
            <span>NOW PLAYING · {playingTrack.participants.join(' + ')}</span>
          </div>
          <div className="mini-player-wave" aria-hidden="true">
            <i /><i /><i /><i /><i /><i /><i /><i /><i />
          </div>
          <button className="mini-player-stop" onClick={stopPlayback} aria-label="音楽を停止">■ STOP</button>
        </aside>
      )}
    </div>
  )
}

export default App
