import { ChefHat, LogOut } from "lucide-react";
import type { User } from "@/lib/types";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ChatView } from "@/components/chat/ChatView";
import { MealPlanView } from "@/components/mealplan/MealPlanView";

export function AppShell({ user }: { user: User }) {
  return (
    <Tabs defaultValue="chat" className="mx-auto flex h-full max-w-3xl flex-col gap-0">
      <header className="flex items-center justify-between gap-4 border-b px-4 py-3">
        <div className="flex items-center gap-2 font-semibold">
          <ChefHat className="size-5 text-primary" />
          Forkcast
        </div>
        <TabsList>
          <TabsTrigger value="chat">Chat</TabsTrigger>
          <TabsTrigger value="plan">Meal Plan</TabsTrigger>
        </TabsList>
        <div className="flex items-center gap-2">
          <span className="hidden text-sm text-muted-foreground sm:inline">
            {user.name ?? user.email}
          </span>
          <a
            href="/auth/logout"
            title="Sign out"
            className={cn(buttonVariants({ variant: "ghost", size: "icon" }))}
          >
            <LogOut className="size-4" />
          </a>
        </div>
      </header>

      {/* keepMounted preserves the chat conversation when switching tabs. */}
      <TabsContent value="chat" keepMounted className="min-h-0 flex-1">
        <ChatView />
      </TabsContent>
      <TabsContent value="plan" keepMounted className="min-h-0 flex-1">
        <MealPlanView />
      </TabsContent>
    </Tabs>
  );
}
