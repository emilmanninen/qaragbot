"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Chat" },
  { href: "/about", label: "About" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="flex w-full justify-center border-b border-border bg-background px-4 py-3">
      <div className="flex w-full max-w-3xl items-center gap-1">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              pathname === item.href
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            {item.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
