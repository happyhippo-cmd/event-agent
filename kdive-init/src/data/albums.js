// 원본 k_dive_onboarding.js의 ALBUMS 배열을 그대로 옮긴 데이터 모듈
export const ALBUMS = [
  { id: 'a1', title: '소문의 낙원', artist: 'AKMU', cover: '/assets/album-covers/akmu-paradise-of-rumors.jpg', vibe: '기묘한 · 자유로운',
    spotifyUri: 'spotify:track:5dxiriLgC9mu2FbSNqudld', preview: '',
    places: [{ name: '문래창작촌', emoji: '🛠️', desc: '낯선 골목과 작업실이 노래의 독특한 상상력을 닮아 있어요.' }, { name: '을지로 골목', emoji: '🪩', desc: '오래된 간판과 새로운 감각이 섞이는 밀도 높은 산책지.' }, { name: '서울책보고', emoji: '📚', desc: '소문과 이야기가 켜켜이 쌓인 듯한 공간.' }] },
  { id: 'a2', title: '0+0', artist: 'HANRORO', cover: '/assets/album-covers/hanroro-0-plus-0.jpg', vibe: '청춘의 · 선명한',
    spotifyUri: 'spotify:track:3sOAwRg5esaxDcWnUigWPv', preview: '',
    places: [{ name: '망원한강공원', emoji: '🌊', desc: '가볍게 뛰어가고 싶은 청춘의 속도와 잘 맞아요.' }, { name: '연희동 골목', emoji: '🌿', desc: '조용하지만 선명한 감정이 남는 동네.' }, { name: '서울숲', emoji: '🌱', desc: '바람과 햇빛이 곡의 싱그러운 긴장감을 살려줘요.' }] },
  { id: 'a3', title: 'Love wins all', artist: 'IU', cover: '/assets/album-covers/iu-love-wins-all.jpg', vibe: '애틋한 · 시네마틱한',
    spotifyUri: 'spotify:track:0djkJ3iAARXRCbfbwwVc3o', preview: '',
    places: [{ name: '덕수궁 돌담길', emoji: '🏛️', desc: '서정적인 감정선을 따라 천천히 걷기 좋은 길.' }, { name: '정동길', emoji: '🕯️', desc: '오래된 건물과 조용한 분위기가 곡의 여운을 살려줘요.' }, { name: '남산 소월길', emoji: '🌃', desc: '도시의 불빛을 멀리 두고 감정에 잠기기 좋은 밤길.' }] },
  { id: 'a4', title: 'RedRed', artist: 'CORTIS', cover: '/assets/album-covers/cortis-redred.jpg', vibe: '날것의 · 강렬한',
    spotifyUri: 'spotify:track:2fCwv2ppU5nTRTckomIGsd', preview: '',
    places: [{ name: '홍대 스트리트', emoji: '🎤', desc: '거친 에너지와 즉흥적인 움직임이 살아 있는 거리.' }, { name: '성수 대림창고', emoji: '🏭', desc: '러프한 질감과 감각적인 전시 무드가 맞물려요.' }, { name: '노들섬', emoji: '🎧', desc: '크게 음악을 틀고 싶어지는 열린 공간.' }] },
  { id: 'a5', title: '404', artist: 'KiiiKiii', cover: '/assets/album-covers/kiiikiii-404.jpg', vibe: '디지털 · 쿨한',
    spotifyUri: 'spotify:track:1rEa59P5yEal5cp1h7kl2e', preview: '',
    places: [{ name: '용산 아이파크몰', emoji: '💿', desc: '디지털 감성과 도시적 동선이 잘 어울려요.' }, { name: '강남역 미디어폴', emoji: '📱', desc: '빛과 광고판 사이로 404의 쿨한 질감이 살아나요.' }, { name: '동대문 디자인 플라자', emoji: '🌀', desc: '곡의 매끈한 미래감과 잘 맞는 야간 코스.' }] },
  { id: 'a6', title: '이브, 프시케, 그리고 푸른 수염의 아내', artist: 'LE SSERAFIM', cover: '/assets/album-covers/lesserafim-eve.jpg', vibe: '당당한 · 대담한',
    spotifyUri: 'spotify:track:4QhnNyKDsAkXPwHkSnuc89', preview: '',
    places: [{ name: '이태원 해방촌', emoji: '🌆', desc: '자유롭고 자신감 있는 무드가 잘 살아나는 언덕길.' }, { name: '압구정 로데오', emoji: '💎', desc: '강한 태도와 화려한 거리감이 어울려요.' }, { name: '여의도 더현대', emoji: '🛍️', desc: '세련된 공간감 속에서 곡의 에너지가 또렷해져요.' }] },
  { id: 'a7', title: '붉은 노을', artist: 'BIGBANG', cover: '/assets/album-covers/bigbang-sunset-glow.jpg', vibe: '레트로 · 벅찬',
    spotifyUri: 'spotify:track:3qHBjPdFZeS0tfXywAxOKq', preview: '',
    places: [{ name: '노을공원', emoji: '🌇', desc: '제목 그대로 붉은 하늘과 함께 듣기 좋은 장소.' }, { name: '반포한강공원', emoji: '🌉', desc: '해질녘부터 밤까지 감정이 크게 번지는 코스.' }, { name: '상암 월드컵경기장', emoji: '🏟️', desc: '큰 후렴처럼 탁 트인 스케일이 있는 공간.' }] },
  { id: 'a8', title: 'RUDE!', artist: 'Hearts2Hearts', cover: '/assets/album-covers/hearts2hearts-rude.jpg', vibe: '키치한 · 발랄한',
    spotifyUri: 'spotify:track:2bAQsNqdo62T8akkIvWzGl', preview: '',
    places: [{ name: '성수 편집숍 거리', emoji: '🛒', desc: '톡톡 튀는 스타일과 신선한 감각이 많은 동네.' }, { name: '홍대 소품샵 골목', emoji: '🎀', desc: '장난스럽고 선명한 컬러감이 곡과 잘 맞아요.' }, { name: '연남동 카페거리', emoji: '🍰', desc: '가볍고 발랄한 무드로 걷기 좋은 코스.' }] },
  { id: 'a9', title: 'Drowning', artist: 'WOODZ', cover: '/assets/album-covers/woodz-drowning.jpg', vibe: '몰입감 있는 · 애절한',
    spotifyUri: 'spotify:track:4xeugB5MqWh0jwvXZPxahq', preview: '',
    places: [{ name: '한강 잠수교', emoji: '🌉', desc: '물과 도시가 겹치는 풍경이 감정의 깊이를 만들어줘요.' }, { name: '북서울꿈의숲', emoji: '🌲', desc: '조용히 걷다 보면 곡의 여운이 길게 남는 곳.' }, { name: '부암동 골목', emoji: '☁️', desc: '차분하고 깊은 분위기가 잘 맞아요.' }] },
  { id: 'a10', title: 'Body to Body', artist: 'BTS', cover: '/assets/album-covers/bts-body-to-body.jpg', vibe: '감각적 · 리드미컬한',
    spotifyUri: 'spotify:track:2rKkfc4VZ74FQDc1FF1Zo6', preview: '',
    places: [{ name: '한강 세빛섬', emoji: '🌊', desc: '물빛과 야경이 겹쳐 리듬감 있는 밤 산책을 만들어요.' }, { name: '성수 팝업 거리', emoji: '✨', desc: '트렌디한 공간과 음악이 자연스럽게 이어지는 코스.' }, { name: 'DDP 동대문', emoji: '🌙', desc: '곡의 세련된 움직임과 잘 어울리는 미래적인 야경 포인트.' }] },
  { id: 'a11', title: 'Blue Valentine', artist: 'NMIXX', cover: '/assets/album-covers/nmixx-blue-valentine.jpg', vibe: '블루한 · 다이내믹한',
    spotifyUri: 'spotify:track:4i0HNuFEH6P6K4UnsY5uUh', preview: '',
    places: [{ name: '청계천', emoji: '💧', desc: '도심 속 푸른 빛과 빠른 리듬이 자연스럽게 만나요.' }, { name: '잠실 석촌호수', emoji: '🌙', desc: '차분한 물가와 밝은 도시감이 함께 있어요.' }, { name: '파라다이스시티', emoji: '💙', desc: '블루 톤의 화려함과 다이내믹한 공간감이 어울려요.' }] },
  { id: 'a12', title: '뛰어', artist: 'BLACKPINK', cover: '/assets/album-covers/blackpink-jump.jpg', vibe: '폭발적인 · 런웨이 같은',
    spotifyUri: 'spotify:track:4JjJ1KNRrzqstSY0uDuys3', preview: '',
    places: [{ name: '잠실 올림픽주경기장', emoji: '🏟️', desc: '큰 무대감과 폭발적인 에너지를 떠올리게 해요.' }, { name: '강남역 대로', emoji: '⚡', desc: '도시의 속도감이 곡의 임팩트를 키워줘요.' }, { name: '더현대 서울', emoji: '🖤', desc: '강한 비주얼과 쇼핑 공간의 스케일이 잘 맞아요.' }] },
  { id: 'a13', title: 'Golden', artist: 'HUNTR/X', cover: '/assets/album-covers/huntrx-golden.jpg', vibe: '영웅적인 · 반짝이는',
    spotifyUri: 'spotify:track:1CPZ5BxNNd0n0nF4Orb9JS', preview: '',
    places: [{ name: '남산서울타워', emoji: '✨', desc: '높이 올라갈수록 곡의 반짝이는 스케일이 살아나요.' }, { name: '경복궁 야간개장', emoji: '🏯', desc: '전통적인 실루엣과 드라마틱한 빛이 잘 어울려요.' }, { name: '롯데월드타워 전망대', emoji: '🌟', desc: '도시 전체가 무대처럼 펼쳐지는 장소.' }] },
  { id: 'a14', title: 'Happy', artist: 'DAY6', cover: '/assets/album-covers/day6-happy.jpg', vibe: '따뜻한 · 벅찬',
    spotifyUri: 'spotify:track:5R5NMy7zc7QPCfdvy8dvCQ', preview: '',
    places: [{ name: '선유도공원', emoji: '🌤️', desc: '밝고 따뜻한 감정이 천천히 차오르는 산책지.' }, { name: '합정 라이브클럽 거리', emoji: '🎸', desc: '밴드 사운드의 생동감을 직접 느끼기 좋은 동네.' }, { name: '서울숲 피크닉존', emoji: '🌿', desc: '가볍게 숨을 고르며 행복한 기분을 오래 가져가기 좋아요.' }] },
  { id: 'a15', title: 'Catch Catch', artist: 'YENA', cover: '/assets/album-covers/yena-catch-catch.jpg', vibe: '키치한 · 통통 튀는',
    spotifyUri: 'spotify:track:2O9bMJticxbQ8FH3NiQ7Xh', preview: '',
    places: [{ name: '성수 팝업 거리', emoji: '💘', desc: '사랑을 잡으러 뛰어다니는 듯한 키치한 에너지가 잘 살아나요.' }, { name: '홍대 소품샵 골목', emoji: '🎀', desc: '장난스럽고 컬러풀한 감성이 곡의 캐치한 후렴과 잘 맞아요.' }, { name: '잠실 롯데월드', emoji: '🎡', desc: '밝고 사랑스러운 긴장감이 놀이공원 무드와 자연스럽게 이어져요.' }] },
  { id: 'a16', title: 'Sticky', artist: 'NCT WISH', cover: '/assets/album-covers/nct-wish-sticky.jpg', vibe: '달콤한 · 트로피컬한',
    spotifyUri: 'spotify:track:7BlYoOdDyBzj3L1XRvRpYr', preview: '',
    places: [{ name: '망원시장', emoji: '🥭', desc: '달콤하고 활기찬 먹거리 동선이 망고 스티키 라이스 같은 곡의 질감과 잘 맞아요.' }, { name: '연남동 디저트 골목', emoji: '🍮', desc: '가벼운 설렘과 달콤한 분위기를 이어가기 좋은 산책 코스.' }, { name: '서울숲 피크닉존', emoji: '🌴', desc: '햇빛과 바람이 곡의 트로피컬한 리듬을 부드럽게 살려줘요.' }] },
  { id: 'a17', title: 'Sugar Rush Ride', artist: 'TXT', cover: '/assets/album-covers/txt-sugar-rush-ride.jpg', vibe: '달콤한 · 몽환적인',
    spotifyUri: 'spotify:track:3T0zu18D6Lr5u1xdxgIG6s', preview: '',
    places: [{ name: '서울숲 온실', emoji: '🍃', desc: '달콤하고 낯선 숲의 이미지가 곡의 몽환적인 질감과 맞아요.' }, { name: '코엑스 아쿠아리움', emoji: '🐠', desc: '빛과 물결 사이로 빠져드는 듯한 감각을 이어가기 좋아요.' }, { name: '연남동 디저트 골목', emoji: '🍰', desc: '사탕처럼 밝은 골목 무드가 후렴의 달콤함을 살려줘요.' }] },
  { id: 'a18', title: 'REBEL HEART', artist: 'IVE', cover: '/assets/album-covers/ive-rebel-heart.jpg', vibe: '당당한 · 찬란한',
    spotifyUri: 'spotify:track:0qdPpfbrgdBs6ie9bTtQ1d', preview: '',
    places: [{ name: '광화문광장', emoji: '🛡️', desc: '크게 열린 축과 도시의 스케일이 당당한 에너지와 잘 맞아요.' }, { name: '잠실 롯데월드타워', emoji: '🏙️', desc: '높고 반짝이는 도시감이 곡의 찬란함을 키워줘요.' }, { name: '압구정 로데오', emoji: '💎', desc: '자신감 있는 스타일과 빠른 동선이 곡의 태도와 어울려요.' }] },
  { id: 'a19', title: 'Rooftop', artist: 'N.Flying', cover: '/assets/album-covers/nflying-rooftop.jpg', vibe: '청량한 · 벅찬',
    spotifyUri: 'spotify:track:2LwH6T39A5IODRgPv9XitR', preview: '',
    places: [{ name: '세운상가 옥상', emoji: '🏢', desc: '도심 위로 올라가 바람을 맞는 감각이 곡의 청량함과 닮았어요.' }, { name: '노들섬 잔디마당', emoji: '🎸', desc: '밴드 사운드처럼 탁 트인 공간감이 살아나는 장소.' }, { name: '한강 잠원지구', emoji: '🌬️', desc: '강바람과 밝은 후렴을 함께 가져가기 좋은 산책 코스.' }] },
  { id: 'a20', title: 'Antifreeze', artist: 'The Black Skirts', cover: '/assets/album-covers/black-skirts-antifreeze.jpg', vibe: '나른한 · 빈티지한',
    spotifyUri: 'spotify:track:1vKfvZpqvjZk560Zub1OUX', preview: '',
    places: [{ name: '부암동 골목', emoji: '☕', desc: '오래된 골목의 조용한 결이 곡의 빈티지한 온도와 잘 맞아요.' }, { name: '필동 카페거리', emoji: '📻', desc: '나른한 오후와 오래된 건물의 질감이 자연스럽게 이어져요.' }, { name: '정동길', emoji: '🍂', desc: '천천히 걷는 속도가 곡의 부드러운 여운을 살려줘요.' }] },
  { id: 'a21', title: 'Into the New World', artist: "Girls' Generation", cover: '/assets/album-covers/girls-generation-into-the-new-world.jpg', vibe: '희망찬 · 찬란한',
    spotifyUri: 'spotify:track:1RTW9UthqmZwr8Od6CH4i8', preview: '',
    places: [{ name: '서울광장', emoji: '🌟', desc: '시작의 설렘과 응원의 에너지가 크게 번지는 열린 공간.' }, { name: '여의도 한강공원', emoji: '🌈', desc: '넓은 하늘 아래 새로운 출발의 감각을 느끼기 좋아요.' }, { name: '이화여대 캠퍼스길', emoji: '📣', desc: '밝고 단단한 청춘의 분위기가 곡의 메시지와 맞아요.' }] },
  { id: 'a22', title: 'The Chaser', artist: 'INFINITE', cover: '/assets/album-covers/infinite-the-chaser.jpg', vibe: '극적인 · 질주하는',
    spotifyUri: 'spotify:track:6fzJaYb6xprozFzFdqfI9s', preview: '',
    places: [{ name: '청계천 야간 산책로', emoji: '🏃', desc: '빠르게 이어지는 도시의 선이 곡의 질주감을 닮았어요.' }, { name: '월드컵대교 전망길', emoji: '🌉', desc: '드라마틱한 구조와 속도감 있는 풍경이 잘 맞아요.' }, { name: '상암 문화비축기지', emoji: '⚙️', desc: '강한 리듬과 금속성 공간감이 함께 살아나요.' }] },
  { id: 'a23', title: '피차일반', artist: '음율', cover: '/assets/album-covers/eumyul-each-other.jpg', vibe: '서정적인 · 단정한',
    spotifyUri: 'spotify:track:5UuOwk4n77Z62CypOgly5n', preview: '',
    places: [{ name: '성북동 길상사', emoji: '🕯️', desc: '조용히 마음을 정리하기 좋은 공간이 서정적인 결을 살려줘요.' }, { name: '연희문학창작촌', emoji: '✍️', desc: '문장처럼 차분한 동선이 곡의 단정한 감정과 어울려요.' }, { name: '경의선숲길', emoji: '🌿', desc: '느린 산책이 노래의 고운 호흡과 맞아요.' }] },
  { id: 'a24', title: '정말 오래도 걸렸네', artist: 'Yudabinband', cover: '/assets/album-covers/yudabinband-long-time.jpg', vibe: '담담한 · 벅찬',
    spotifyUri: 'spotify:track:07e1gjMxsEert6GeL02m6t', preview: '',
    places: [{ name: '망원한강공원', emoji: '🌊', desc: '천천히 차오르는 감정과 강변의 넓은 공기가 잘 맞아요.' }, { name: '서촌 골목', emoji: '🏘️', desc: '오래 걸어온 이야기를 떠올리게 하는 조용한 골목.' }, { name: '홍대 라이브클럽 거리', emoji: '🎙️', desc: '밴드의 진심이 가까이 들리는 듯한 공간감이 있어요.' }] },
  { id: 'a25', title: 'Bounce', artist: 'Cho Yong Pil', cover: '/assets/album-covers/cho-yong-pil-bounce.jpg', vibe: '경쾌한 · 클래식한',
    spotifyUri: 'spotify:track:4aa6QK7mtuYuVcAeTSSOb7', preview: '',
    places: [{ name: '청춘극장', emoji: '🎞️', desc: '세대를 잇는 팝 감각과 레트로한 활기가 잘 어울려요.' }, { name: '명동 거리', emoji: '🚶', desc: '밝고 익숙한 도시 리듬이 곡의 경쾌함을 살려줘요.' }, { name: '반포한강공원', emoji: '🎆', desc: '불빛과 사람들의 움직임이 후렴의 탄력을 닮았어요.' }] },
  { id: 'a26', title: 'T.B.H', artist: 'QWER', cover: '/assets/album-covers/qwer-tbh.jpg', vibe: '싱그러운 · 풋풋한',
    spotifyUri: 'spotify:track:39gaUtq2z4ejJbno7tWHbL', preview: '',
    places: [{ name: '서울숲 피크닉존', emoji: '🌱', desc: '풋풋한 밴드 사운드와 초록빛 공기가 잘 맞아요.' }, { name: '연남동 카페거리', emoji: '🍓', desc: '상큼한 분위기로 가볍게 걷기 좋은 동네.' }, { name: '한강 난지공원', emoji: '🧺', desc: '밝은 리듬을 야외에서 오래 가져가기 좋아요.' }] },
  { id: 'a28', title: 'Super', artist: 'SEVENTEEN', cover: '/assets/album-covers/seventeen-super.jpg', vibe: '웅장한 · 에너제틱한',
    spotifyUri: 'spotify:track:3AOf6YEpxQ894FmrwI9k96', preview: '',
    places: [{ name: '잠실 올림픽주경기장', emoji: '🏟️', desc: '큰 퍼포먼스의 스케일을 그대로 느낄 수 있는 공간.' }, { name: '광화문광장', emoji: '🔥', desc: '웅장한 직선과 열린 풍경이 강한 에너지를 받아줘요.' }, { name: 'DDP 동대문', emoji: '⚡', desc: '미래적인 곡선이 퍼포먼스의 속도감과 잘 맞아요.' }] },
  { id: 'a29', title: 'NO PAIN', artist: 'Silica Gel', cover: '/assets/album-covers/silica-gel-no-pain.jpg', vibe: '사이키델릭 · 폭발적인',
    spotifyUri: 'spotify:track:4ceXU11FfeiQ47B4cX28gB', preview: '',
    places: [{ name: '을지로 철공소 골목', emoji: '🔩', desc: '거친 질감과 네온빛이 실험적인 사운드와 잘 맞아요.' }, { name: '문래창작촌', emoji: '🌀', desc: '작업실과 공장이 섞인 풍경이 밴드의 에너지를 살려줘요.' }, { name: '노들섬 라이브하우스', emoji: '🎛️', desc: '소리의 밀도와 현장감이 크게 느껴지는 코스.' }] },
  { id: 'a30', title: '그때 그 사람', artist: '심수봉', cover: '/assets/album-covers/sim-soo-bong-the-man-at-then.jpg', vibe: '레트로 · 애잔한',
    spotifyUri: 'spotify:track:0EF6kGs8t5ZwGRZ2Tbn7IJ', preview: '',
    places: [{ name: '인사동 골목', emoji: '🌺', desc: '오래된 정서와 애잔한 멜로디가 자연스럽게 겹쳐져요.' }, { name: '익선동 한옥거리', emoji: '🏮', desc: '레트로한 불빛과 좁은 골목이 곡의 여운을 살려줘요.' }, { name: '낙산공원 성곽길', emoji: '🌙', desc: '밤공기와 오래된 서울의 실루엣이 잘 어울려요.' }] },
  { id: 'a31', title: 'Aqua Man', artist: 'Beenzino', cover: '/assets/album-covers/beenzino-aqua-man.jpg', vibe: '쿨한 · 도회적인',
    spotifyUri: 'spotify:track:5tEouf2s1SPwAIkOHnvWtQ', preview: '',
    places: [{ name: '압구정 로데오', emoji: '🕶️', desc: '세련된 거리감과 랩의 쿨한 태도가 잘 맞아요.' }, { name: '한남동 카페거리', emoji: '☕', desc: '도회적인 무드와 느슨한 리듬을 함께 즐기기 좋아요.' }, { name: '성수 대림창고', emoji: '🧊', desc: '차갑고 감각적인 공간 질감이 곡의 색과 어울려요.' }] },
  { id: 'a32', title: '스물다섯, 스물하나', artist: 'JAURIM', cover: '/assets/album-covers/jaurim-twenty-five-twenty-one.jpg', vibe: '청춘의 · 아련한',
    spotifyUri: 'spotify:track:3DmDPYRQYdYE5gWf2DiKn2', preview: '',
    places: [{ name: '덕수궁 돌담길', emoji: '🍂', desc: '지나간 계절을 떠올리게 하는 길이 곡의 아련함과 닮았어요.' }, { name: '정동길', emoji: '📷', desc: '청춘의 한 장면처럼 남는 조용한 거리.' }, { name: '여의도 샛강생태공원', emoji: '🌾', desc: '조용한 바람과 긴 여운이 잘 어울려요.' }] },
  { id: 'a33', title: 'Gangnam Style', artist: 'PSY', cover: '/assets/album-covers/psy-gangnam-style.jpg', vibe: '축제적인 · 유쾌한',
    spotifyUri: 'spotify:track:03UrZgTINDqvnUMbbIMhql', preview: '',
    places: [{ name: '강남역 대로', emoji: '🕺', desc: '사람과 불빛이 몰리는 에너지가 곡의 유쾌함과 직결돼요.' }, { name: '코엑스 별마당길', emoji: '🎉', desc: '관광객과 도시의 활기가 크게 느껴지는 동선.' }, { name: '잠실 롯데월드', emoji: '🎠', desc: '과장되고 밝은 즐거움을 그대로 이어가기 좋은 장소.' }] },
  { id: 'a34', title: 'Touch', artist: 'KATSEYE', cover: '/assets/album-covers/katseye-touch.jpg', vibe: '글로벌 · 산뜻한',
    spotifyUri: 'spotify:track:1I5whYZ5CmnVtHKKoy4Im5', preview: '',
    places: [{ name: '이태원 세계음식거리', emoji: '🌐', desc: '여러 문화가 자연스럽게 섞이는 거리가 캣츠아이의 글로벌한 무드와 잘 맞아요.' }, { name: '성수 편집숍 거리', emoji: '💅', desc: '산뜻하고 감각적인 동선이 곡의 가벼운 리듬을 살려줘요.' }, { name: '한강 반포 무지개분수', emoji: '💦', desc: '밝은 물빛과 도시 야경이 Touch의 반짝이는 후렴과 어울려요.' }] },
];

export const MUST_VISIT_PLACES = [
  { name: '경복궁', emoji: '🏯', category: 'must', label: '필수', desc: '처음 한국을 여행한다면 꼭 지나가야 할 대표 궁궐이에요. 전통적인 선과 도시의 현재가 한 화면에 겹쳐져요.' },
  { name: '남산서울타워', emoji: '🗼', category: 'must', label: '필수', desc: '서울의 높이와 야경을 한 번에 느낄 수 있는 필수 전망 포인트예요.' },
  { name: '북촌한옥마을', emoji: '🏘️', category: 'must', label: '필수', desc: '한옥 골목을 따라 걷다 보면 오래된 서울의 결을 가까이서 만날 수 있어요.' },
  { name: '광장시장', emoji: '🥢', category: 'must', label: '필수', desc: '먹거리와 시장의 활기가 압축된 장소라 여행의 감각을 빠르게 깨워줘요.' },
  { name: 'DDP 동대문', emoji: '🌙', category: 'must', label: '필수', desc: '서울의 미래적인 곡선과 야간 조명이 강하게 남는 대표 디자인 스팟이에요.' },
];

export const FOOD_TYPES = ['로컬 한식집', '브런치 카페', '분식 스팟', '디저트 바', '야식 맛집'];
export const FOOD_RESULT_LIMIT = 5;
export const MIN_TRACK_SELECTION = 3;
export const MIN_PLACE_SELECTION = 3;
export const PLAYBACK_DURATION_MS = 30000;
export const VISIBLE_EDGE = 5;
export const VISIBLE_OFFSETS = Array.from({ length: VISIBLE_EDGE * 2 + 1 }, (_, i) => i - VISIBLE_EDGE);

export function normalizeAlbumIndex(index) {
  return ((index % ALBUMS.length) + ALBUMS.length) % ALBUMS.length;
}

export function getRecommendedPlaces(album) {
  if (!album) return [];
  const keywordPlaces = album.places.map((place) => ({ ...place, category: 'keyword', label: '음악' }));
  const keywordNames = new Set(keywordPlaces.map((p) => p.name));
  const mustPlaces = MUST_VISIT_PLACES.filter((p) => !keywordNames.has(p.name)).slice(0, 2);
  return [...mustPlaces, ...keywordPlaces].slice(0, 5);
}

export function createFoodSuggestionsForPlace(album, place) {
  return FOOD_TYPES.map((type, index) => ({
    key: `${album.id}::${place.name}::${type}`,
    type,
    placeName: place.name,
    title: `${place.name} 근처 ${type}`,
    desc: `${album.vibe} 무드로 이어가기 좋은 동선의 맛집 후보 ${index + 1}번이에요.`,
    curation: `${place.name}을 둘러본 뒤 바로 이어가기 좋은 코스예요. 음악의 ${album.vibe} 감정선을 유지하면서 식사, 디저트, 밤 산책까지 자연스럽게 연결할 수 있어요.`,
  }));
}

export function getPlaceKey(albumId, placeName) {
  return `${albumId}::${placeName}`;
}

export function getPlaceSelectionKey(albumId, place) {
  return place?.key || getPlaceKey(albumId, place?.name || '');
}
