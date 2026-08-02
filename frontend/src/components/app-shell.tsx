"use client";

import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { NavBar } from "@/components/nav-bar";
import { ChatView } from "@/components/chat-view";

// ChatView is rendered here (outside the routed `children` tree) and only
// ever hidden via CSS, never unmounted — the App Router remounts route
// segments on navigation, which would otherwise wipe the chat's in-memory
// message history every time the user visits "About" and comes back.
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isChatRoute = pathname === "/";

  return (
    <>
      <NavBar />
      <div className={cn("flex flex-1 flex-col", !isChatRoute && "hidden")}>
        <ChatView />
      </div>
      <div className={cn("flex flex-1 flex-col", isChatRoute && "hidden")}>
        {children}
      </div>
    </>
  );
}
