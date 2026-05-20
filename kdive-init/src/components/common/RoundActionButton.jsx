'use client';

const VARIANT_STYLES = {
  like: {
    base: 'border-0 bg-transparent',
    active: 'text-heart',
    inactive: 'text-[rgba(0,0,0,0.16)] hover:text-[rgba(0,0,0,0.36)]',
    icon: { active: '♥', inactive: '♡' },
    iconClass: { active: '', inactive: 'font-normal' },
  },
  visited: {
    base: 'border',
    active: 'border-[#2d8c5d] bg-[#2d8c5d] text-white',
    inactive: 'border-[rgba(0,0,0,0.16)] bg-white text-[rgba(0,0,0,0.16)] hover:border-[rgba(0,0,0,0.36)] hover:text-[rgba(0,0,0,0.36)]',
    icon: { active: '✓', inactive: '✓' },
    iconClass: { active: 'translate-y-[2px]', inactive: 'translate-y-[2px]' },
  },
};

export default function RoundActionButton({
  variant = 'like',
  active = false,
  label,
  onClick,
  className = '',
}) {
  const style = VARIANT_STYLES[variant] || VARIANT_STYLES.like;
  const stateClass = active ? style.active : style.inactive;
  const iconClass = active ? style.iconClass.active : style.iconClass.inactive;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      className={`flex aspect-square flex-shrink-0 items-center justify-center rounded-full text-[18px] font-bold leading-none transition-all hover:scale-105 ${style.base} ${stateClass} ${className}`}
    >
      <span className={`block ${iconClass}`}>
        {active ? style.icon.active : style.icon.inactive}
      </span>
    </button>
  );
}
