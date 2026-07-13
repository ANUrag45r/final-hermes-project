import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/lib/theme";
import { Sidebar } from "@/components/Sidebar";
import { Dashboard } from "@/pages/Dashboard";
import { Meetings } from "@/pages/Meetings";
import { MeetingDetail } from "@/pages/MeetingDetail";
import { Chat } from "@/pages/Chat";
import { Reports } from "@/pages/Reports";
import { Contact } from "@/pages/Contact";
import { Agent } from "@/pages/Agent";
import { Skills } from "@/pages/Skills";

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <div className="flex h-screen overflow-hidden bg-paper">
          <Sidebar />
          <main className="flex-1 overflow-hidden">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/meetings" element={<Meetings />} />
              <Route path="/meetings/:id" element={<MeetingDetail />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/skills" element={<Skills />} />
              <Route path="/contact" element={<Contact />} />
              <Route path="/agent" element={<Agent />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </ThemeProvider>
  );
}
