'use client';

import { ALBUMS } from '@/data/albums';
import { useKdive } from '@/store/KdiveContext';

export default function DeckDots() {
  const { currentIdx, goToIndex } = useKdive();

  return (
    <div className="flex gap-[5px] items-center">
      {ALBUMS.map((album, i) => (
        <button
          key={album.id}
          type="button"
          onClick={() => goToIndex(i)}
          aria-label={`${album.title}로 이동`}
          className={`h-[6px] rounded-full transition-all cursor-pointer border-0 p-0 ${
            i === currentIdx ? 'w-4 bg-accent rounded' : 'w-[6px] bg-[rgba(0,0,0,0.08)]'
          }`}
        />
      ))}
    </div>
  );
}
