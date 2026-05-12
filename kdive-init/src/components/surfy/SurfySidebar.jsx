'use client';

import { useSurfyChat } from './surfyChatStore';

export default function SurfySidebar() {
  const { chats, activeChatId, switchChat, createNewChat } = useSurfyChat();

  return (
    <aside className="fixed top-[61px] left-0 bottom-0 z-[70] w-[260px] bg-white border-r border-[rgba(0,0,0,0.08)] px-3 py-[22px] flex flex-col gap-4 max-[768px]:w-[210px] max-[768px]:px-[10px] max-[768px]:py-[14px] max-[620px]:hidden">
      <button type="button" aria-label="채팅 기록 검색" className="w-full h-[46px] border border-[rgba(0,0,0,0.08)] rounded-[18px] bg-white text-muted flex items-center justify-start gap-[14px] px-[18px] font-pretendard text-[15px] cursor-pointer">
        <span className="relative w-[14px] h-[14px] flex-shrink-0 border-2 border-muted rounded-full">
          <span className="absolute -right-[5px] -bottom-[3px] w-[7px] h-[1.8px] bg-muted rounded-full rotate-45 origin-center" />
        </span>
        <span>Search...</span>
      </button>
      <button
        type="button"
        onClick={createNewChat}
        className="w-full h-[46px] border-0 rounded-[16px] bg-accent text-white font-pretendard text-[14px] font-bold flex items-center justify-center gap-2 cursor-pointer shadow-[0_10px_22px_rgba(0,168,232,0.18)]"
      >
        <span className="text-[20px] leading-none -translate-y-px">+</span> 새 대화
      </button>
      <div className="flex flex-col gap-2 min-h-0 mt-1" aria-label="대화 목록">
        <p className="px-3 pb-1 text-muted text-[11px] font-bold tracking-[0.12em] uppercase">Recent chats</p>
        {chats.map((chat) => (
          <button
            key={chat.id}
            type="button"
            data-chat-id={chat.id}
            onClick={() => switchChat(chat.id)}
            className={`w-full min-h-[66px] border-0 rounded-[16px] text-left px-[14px] py-3 cursor-pointer transition-all ${chat.id === activeChatId ? 'bg-accent-soft' : 'bg-transparent hover:bg-accent-soft'}`}
          >
            <strong className="block mb-[6px] text-[14px] leading-[1.2]">{chat.title}</strong>
            <span className="block text-muted text-[12px] leading-[1.25] whitespace-nowrap overflow-hidden text-ellipsis">
              {chat.preview}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
