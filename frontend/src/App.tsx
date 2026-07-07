import { Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { LoginPage } from "@/components/LoginPage";
import { AppShell } from "@/components/AppShell";

export default function App() {
  const auth = useAuth();

  if (auth.status === "loading") {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (auth.status === "authed") return <AppShell user={auth.user} />;

  if (auth.status === "error") {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground">
        Couldn't reach the server. {auth.message}
      </div>
    );
  }

  return <LoginPage />;
}
