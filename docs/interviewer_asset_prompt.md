# 면접관 이미지/영상 생성 가이드 (Interviewer asset prompts)

이 문서는 면접 룸에 넣을 **실제 사람 같은 면접관**을 외부 생성형 모델
(Midjourney, DALL·E, Stable Diffusion, Kling, Runway, Sora 등)로 만들 때
그대로 복사해서 쓸 수 있는 프롬프트 모음입니다.

앱은 두 가지 형식을 지원합니다.

- **정지 사진 한 장** (`.png .jpg .jpeg .webp .bmp`) — 앱이 미세한 "숨쉬기 줌"
  애니메이션을 자동으로 입혀 살아있는 느낌을 줍니다. **가장 간단하고 권장하는 방식**입니다.
- **영상 파일** (`.mp4 .avi .mov .mkv`) — 말하는 모션이 담긴 클립. 더 사실적이지만
  파일이 크고 제작이 번거롭습니다.

만든 파일은 **미디어 설정 → 영상/사진** 에서 선택하면 됩니다. 기본 경로에
`assets/interviewer.mp4`(또는 사진)로 두면 자동으로 잡힙니다.

---

## 1. 프레이밍/기술 사양 (먼저 읽어주세요)

면접관 스테이지는 가로형(약 16:9)이고, 앱이 이미지를 **꽉 채운 뒤 가운데를
기준으로 크롭**합니다. 아래 사양을 지키면 잘림 없이 깔끔하게 들어갑니다.

| 항목 | 권장값 |
|---|---|
| 종횡비 | **16:9** (가로) |
| 해상도 | 1920×1080 이상 (사진) / 1280×720 이상 (영상) |
| 구도 | 가슴 위 상반신(medium shot), 인물 **정중앙**, 카메라 정면 응시 |
| 여백 | 머리 위·좌우에 약간 여유 — 숨쉬기 줌으로 살짝 확대되므로 |
| 배경 | 흐릿한(bokeh) 사무실/면접실. 글자·로고·창밖 강한 빛 금지 |
| 표정 | 차분하고 정중한 미소, 위협적이지 않은 눈맞춤 |
| 금지 | 워터마크, 텍스트, 손 제스처 과다, 과장된 표정, 왜곡된 손/눈 |

> 팁: 숨쉬기 줌이 최대 약 2% 확대되므로, 인물을 프레임 **끝까지 꽉 채우지 말고**
> 머리 위에 약간의 헤드룸을 두세요.

---

## 2. 정지 사진 프롬프트 (권장)

### 2-A. 한국어 여성 면접관 (기본 화자 "Sohee"와 어울림)

```
Professional corporate headshot of a poised Korean woman in her early 40s,
senior HR interviewer, seated at an interview table, medium shot from chest up,
centered composition, facing the camera with calm confident eye contact and a
warm reassuring closed-lip smile. Wearing a tailored navy blazer over a white
blouse. Soft neutral studio key light, gentle rim light, shallow depth of field,
blurred modern office background with soft bokeh. Photorealistic, natural skin
texture, 85mm lens look, 16:9 horizontal framing, high detail, editorial quality.
```

### 2-B. 영어 남성 면접관 (기본 화자 "Ryan"과 어울림)

```
Professional corporate headshot of a distinguished man in his late 40s, senior
hiring manager, seated at an interview table, medium shot from chest up, centered
composition, facing the camera with steady neutral-confident gaze and a subtle
professional smile. Wearing a charcoal suit with a light blue shirt, no tie.
Soft neutral studio key light, gentle rim light, shallow depth of field, blurred
corporate office background with soft bokeh. Photorealistic, natural skin texture,
85mm lens look, 16:9 horizontal framing, high detail, editorial quality.
```

### 2-C. 공통 네거티브 프롬프트 (Stable Diffusion 등에서 사용)

```
cartoon, illustration, 3d render, cgi, plastic skin, over-smooth, uncanny,
deformed face, extra fingers, distorted hands, text, watermark, logo, signature,
harsh shadows, blown highlights, wide-angle distortion, tilted horizon, low
resolution, jpeg artifacts
```

### 2-D. Midjourney 파라미터 예시

프롬프트 뒤에 붙이세요:

```
--ar 16:9 --style raw --stylize 150 --quality 2 --v 6
```

---

## 3. 말하는 영상 프롬프트 (선택)

정지 사진으로 시작해 영상으로 확장하고 싶다면, 위 2-A/2-B에서 만든 이미지를
image-to-video 모델(Kling, Runway Gen-3, Luma, Sora 등)에 넣고 아래 모션
프롬프트를 사용하세요.

```
The interviewer sits calmly and speaks naturally to the camera, subtle mouth
movement as if asking a question, gentle head nods, slow relaxed blinking, very
slight body sway. Keep the framing static and centered, steady camera, no zoom,
no cuts. Professional, composed, reassuring demeanor. Loopable, seamless start
and end.
```

권장 설정: 길이 5~10초, 루프 가능(seamless loop), 카메라 고정, 720p 이상,
mp4(H.264). 앱은 영상을 자동 반복 재생하므로 **끊김 없는 루프**가 이상적입니다.

---

## 4. 앱에 넣는 방법

1. 위 프롬프트로 사진 1장(또는 영상 1개)을 생성해 PC에 저장합니다.
2. 앱 실행 → 인터뷰 화면 하단 **설정** 패널 → **미디어** 탭.
3. **영상/사진** 항목의 **찾아보기**로 생성한 파일을 선택합니다.
4. 면접을 시작하면 스테이지에 인물이 표시됩니다. 사진이면 숨쉬기 줌이,
   영상이면 클립이 자동 재생됩니다. 스테이지를 **더블클릭**하면 전체 화면.

기본값으로 두고 싶다면 파일을 프로그램 폴더의
`assets/interviewer.mp4`(영상) 또는 `assets/interviewer.png`(사진)로 저장하고
미디어 설정에서 해당 경로를 지정하면 됩니다.

---

## 5. 품질 체크리스트

- [ ] 16:9 가로, 인물이 정중앙에 있고 머리 위 여백이 있는가
- [ ] 정면을 보고 있고 표정이 차분·정중한가 (과장/위협 없음)
- [ ] 배경에 글자·로고·워터마크가 없는가
- [ ] 손·눈·귀 등에 생성 오류(왜곡)가 없는가
- [ ] (영상) 5~10초, 루프가 끊기지 않는가
