'use client';

// 페이지 전환 시 위에서 아래로 슬라이드되는 오버레이.
// 현재는 정적으로 렌더만 하고, 필요 시 외부에서 className 토글로 entering/leaving 제어.
export default function TransitionOverlay() {
  return <div id="transition-overlay" className="kd-transition-overlay" />;
}
