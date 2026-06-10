# AI Interviewer

Python/Tkinter 기반 AI 면접관 앱입니다. 질문 리스트를 붙여넣으면 번호 prefix를 정리해서 Qwen3-TTS로 읽고, 질문별 답변 시간과 메모를 CSV/JSON으로 저장합니다.

## 주요 기능

- 질문 입력 또는 `.txt`/`.csv` 파일 불러오기
- `1.`, `1)`, `1.2.`, `Q1.` 같은 질문 번호 prefix 제거
- 한국어/영어 자동 감지
- Qwen3-TTS CustomVoice 기반 TTS
- 질문별 TTS 시작/종료, 답변 시작/종료, 답변 시간, 다시 듣기 횟수, 메모 저장
- 다시 듣기, 이전/다음, TTS 중지, 다시하기, 저장 폴더 열기
- PyInstaller `onedir` EXE 빌드 지원

## 설치

권장 환경은 Windows, Python 3.12입니다. 기본 TTS 엔진은 Qwen3-TTS입니다. Qwen을 설치하지 않았거나 느리면 앱의 `TTS 엔진`에서 `Windows 기본 음성`을 선택하세요.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt
```

`py` 런처가 없는 환경에서는 설치된 Python 3.12 실행 파일로 같은 명령을 실행하세요.

## Qwen3-TTS 선택 설치

Qwen3-TTS는 기본 음성 엔진입니다. GPU/CUDA 환경이 준비되어 있어야 자연스러운 한국어/영어 음성을 사용할 수 있습니다.

```powershell
python -m pip install -r requirements-qwen.txt
```

CUDA용 PyTorch 설치가 별도로 필요할 수 있습니다. 사용 중인 CUDA 버전에 맞는 PyTorch 설치 명령은 PyTorch 공식 설치 페이지 기준으로 적용하세요.

모델 가중치는 EXE에 포함하지 않습니다. 기본 위치는 프로젝트 또는 배포 폴더의 `models/`입니다.

```powershell
.\scripts\download_models.ps1 -Size 0.6B
```

더 높은 품질이 필요하면:

```powershell
.\scripts\download_models.ps1 -Size 1.7B
```

앱은 다음 폴더 구조를 기대합니다.

```text
models/
  Qwen3-TTS-Tokenizer-12Hz/
  Qwen3-TTS-12Hz-0.6B-CustomVoice/
```

## 실행

```powershell
python -m ai_interviewer
```

세션 기록은 기본적으로 다음 위치에 저장됩니다.

```text
%USERPROFILE%\Documents\AIInterview\sessions\<session_id>\
```

각 세션 폴더에는 `session.csv`, `session.json`, `audio_cache/`가 생성됩니다.

## EXE 빌드

```powershell
python -m pip install -r requirements-dev.txt
pyinstaller --noconfirm interview_app.spec
```

빌드 후:

```text
dist/
  AIInterview/
    AIInterview.exe
    models/
      Qwen3-TTS-Tokenizer-12Hz/
      Qwen3-TTS-12Hz-0.6B-CustomVoice/
```

`models/` 폴더는 직접 복사하거나 배포 패키지에 함께 포함하세요. 대형 모델을 PyInstaller 내부에 묶지 않는 것이 안정적입니다.

## 테스트

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```

## 소리가 안 날 때

앱 오른쪽 아래의 `소리 테스트`와 `TTS 진단`을 먼저 누르세요.

- `소리 테스트`도 안 들리면 Windows 출력 장치/볼륨/음소거 문제입니다.
- `TTS 진단`에서 `qwen_tts`, `torch`, `soundfile`, `CUDA` 중 `MISSING` 또는 `NOT AVAILABLE`이 있으면 의존성 또는 GPU 설정 문제입니다.
- Qwen3-TTS가 실패하면 앱은 Windows SAPI 음성 fallback을 사용해서 WAV를 만들고 재생합니다.
- 바로 소리가 나는 기본 Windows 음성이 필요하면 앱의 `TTS 엔진`에서 `Windows 기본 음성`을 선택하세요.
- 생성된 WAV는 세션 폴더의 `audio_cache/`에 저장됩니다. `저장 폴더` 버튼으로 직접 확인할 수 있습니다.

CMD에서 빠르게 의존성을 확인하려면:

```cmd
cd /d C:\bongkj\Projects\AI_Interview
python -c "import torch, qwen_tts, soundfile; print('cuda=', torch.cuda.is_available())"
```

위 명령이 실패하면 현재 앱을 실행하는 Python 환경에 Qwen 의존성이 없는 것입니다. 같은 CMD/conda 환경에서 다음을 실행하세요.

```cmd
cd /d C:\bongkj\Projects\AI_Interview
python -m pip install -r requirements-qwen.txt
python -c "import qwen_tts, soundfile, torch, huggingface_hub; print('qwen ok, cuda=', torch.cuda.is_available(), 'hub=', huggingface_hub.__version__)"
```
