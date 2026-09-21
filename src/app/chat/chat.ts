import { Component, ElementRef, ViewChild, AfterViewChecked, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import * as XLSX from 'xlsx';
import { QueryService, ChatSessionInfo, ChatMessageOut, ChatMessageSource } from '../services/query';
import { MarkdownPipe } from '../markdown.pipe';
interface DisplayMessage {
  role: 'user' | 'assistant';
  text?: string;
  loading?: boolean;
  error?: string;
  records?: any[];
  sourceNote?: string;
  sources?: ChatMessageSource[];
  copied?: boolean;
}

interface ChatSession {
  id: string;
  title: string;
  createdAt: Date;
  messages: DisplayMessage[];
  loaded: boolean;
  messageCount: number;
}

interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onend: (() => void) | null;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, MarkdownPipe],
  templateUrl: './chat.html',
  styleUrl: './chat.scss'
})
export class ChatComponent implements AfterViewChecked {
  @ViewChild('messageList') messageListRef?: ElementRef<HTMLDivElement>;
  @ViewChild('composerInput') composerInputRef?: ElementRef<HTMLTextAreaElement>;

  sessions: ChatSession[] = [];
  activeSessionId: string | null = null;

  input = '';
  sidebarCollapsed = false;
  mobileDrawerOpen = false;
  isRecording = false;
  speechSupported = true;

promptCards: { icon: string; title: string; desc: string; prompt: string }[] = [
    { icon: 'trending-up', title: 'Sales Performance', desc: 'Total sales this month', prompt: 'What is the total sales value this month?' },
    { icon: 'users', title: 'Customer Relationships', desc: 'Which customers need attention?', prompt: 'Which customers have not been contacted recently?' },
    { icon: 'activity', title: 'Employee Activity', desc: 'Team performance this week', prompt: 'Show me team performance this week' },
    { icon: 'target', title: 'Pipeline Health', desc: 'Opportunities by stage', prompt: 'Show me opportunities by pipeline stage' },
    { icon: 'wallet', title: 'Collections', desc: 'Outstanding payments', prompt: 'Which customers have pending payments?' },
    { icon: 'shield-check', title: 'CRM Health', desc: 'Stale customers this month', prompt: 'How many stale customers do we have?' },
  ];

  private shouldScroll = false;
  private recognition?: SpeechRecognitionLike;

  constructor(private queryService: QueryService, private cdr: ChangeDetectorRef) {
if (typeof window !== 'undefined' && window.innerWidth < 1024) {
      this.sidebarCollapsed = true;
    }
    this.setupSpeechRecognition();
    this.loadSessions();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll) {
      this.scrollToBottom();
      this.shouldScroll = false;
    }
  }

  // ---------- Sessions (backend-persisted) ----------

private loadSessions(): void {
    // Populate the sidebar history, but never auto-open the most recent
    // one — landing on Ask AI (or reloading) always starts at a blank
    // "new chat" draft, per explicit preference.
    this.queryService.listSessions().subscribe({
      next: (list) => {
        this.sessions = list.map(s => ({
          id: s.id, title: s.title, createdAt: new Date(s.created_at), messages: [], loaded: false,
          messageCount: s.message_count,
        }));
        this.activeSessionId = null;
        this.cdr.detectChanges();
      },
      error: () => {
        this.sessions = [];
        this.activeSessionId = null;
        this.cdr.detectChanges();
      },
    });
  }

  get activeSession(): ChatSession | undefined {
    return this.sessions.find(s => s.id === this.activeSessionId);
  }

  get showEmptyState(): boolean {
    const s = this.activeSession;
    return !s || s.messages.length === 0;
  }

  get groupedSessions(): { label: string; sessions: ChatSession[] }[] {
    const groups: Record<string, ChatSession[]> = { Today: [], Yesterday: [], Previous: [] };
    const sorted = [...this.sessions].sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
    for (const s of sorted) groups[this.bucketFor(s.createdAt)].push(s);
    return ['Today', 'Yesterday', 'Previous']
      .map(label => ({ label, sessions: groups[label] }))
      .filter(g => g.sessions.length > 0);
  }

  private bucketFor(date: Date): 'Today' | 'Yesterday' | 'Previous' {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diffDays = Math.round((startOfToday.getTime() - startOfDate.getTime()) / 86400000);
if (diffDays <= 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    return 'Previous';
  }

  sessionDateLabel(date: Date): string {
    const bucket = this.bucketFor(date);
    if (bucket !== 'Previous') return bucket;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  sessionMessageLabel(session: ChatSession): string {
    const count = session.messageCount || 0;
    return `${count} ${count === 1 ? 'Message' : 'Messages'}`;
  }

  startNewChat(): void {
    // No backend call here — a session is only created once a first
    // message is actually sent, so idle "New chat" clicks don't litter
    // the history with empty rows.
    this.activeSessionId = null;
    this.input = '';
    this.closeMobileDrawer();
  }

  selectSession(id: string): void {
    this.activeSessionId = id;
    this.closeMobileDrawer();

    const session = this.activeSession;
    if (session && !session.loaded) {
      this.queryService.getMessages(id).subscribe(msgs => {
     session.messages = msgs.map((m: ChatMessageOut) => ({
          role: m.role,
          text: m.content || undefined,
          records: m.records || undefined,
          sourceNote: m.source_note || undefined,
          sources: m.sources || undefined,
        }));
        session.loaded = true;
        this.shouldScroll = true;
        this.cdr.detectChanges();
      });
    } else {
      this.shouldScroll = true;
    }
  }

  // ---------- UI state ----------

toggleSidebar(): void { this.sidebarCollapsed = !this.sidebarCollapsed; }
  openMobileDrawer(): void { this.mobileDrawerOpen = true; }
  closeMobileDrawer(): void { this.mobileDrawerOpen = false; }

  // The sidebar-top button means two different things depending on
  // viewport: on mobile it's inside an overlay drawer, so it should
  // close that drawer; on desktop it collapses the docked sidebar.
  // Those are two different state variables — toggleSidebar() alone
  // has no visible effect on mobile since the drawer's visibility is
  // driven entirely by mobileDrawerOpen, not sidebarCollapsed.
onSidebarToggleClick(): void {
    if (typeof window !== 'undefined' && window.innerWidth < 1024) {
      this.closeMobileDrawer();
    } else {
      this.toggleSidebar();
    }
  }

  autoGrow(textarea: HTMLTextAreaElement): void {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  }

  onComposerKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  // ---------- Sending / regenerating ----------

  send(question?: string): void {
    const text = (question ?? this.input).trim();
    if (!text) return;

    if (!this.activeSessionId) {
      // Lazily create the real backend session on first message only.
      this.queryService.createSession().subscribe(s => {
        const session: ChatSession = {
          id: s.id, title: s.title, createdAt: new Date(s.created_at), messages: [], loaded: true,
          messageCount: 0,
        };
        this.sessions.unshift(session);
        this.activeSessionId = session.id;
        this.sendToSession(session, text);
      });
      return;
    }

    const session = this.activeSession;
    if (!session) return;
    this.sendToSession(session, text);
  }

  private sendToSession(session: ChatSession, text: string): void {
    session.messages.push({ role: 'user', text });
    const loadingMsg: DisplayMessage = { role: 'assistant', loading: true };
    session.messages.push(loadingMsg);

    this.input = '';
    if (this.composerInputRef) this.composerInputRef.nativeElement.style.height = 'auto';
    this.shouldScroll = true;
    this.cdr.detectChanges();

    this.queryService.sendMessage(session.id, text).subscribe({
next: (result) => {
       loadingMsg.loading = false;
        loadingMsg.text = result.content || undefined;
        loadingMsg.records = result.records || undefined;
        loadingMsg.sourceNote = result.source_note || undefined;
        loadingMsg.sources = result.sources || undefined;
        session.messageCount += 2;
        this.shouldScroll = true;
        this.cdr.detectChanges();

        if (session.messages.filter(m => m.role === 'user').length === 1) {
          this.queryService.listSessions().subscribe(list => {
            const updated = list.find(s => s.id === session.id);
            if (updated) session.title = updated.title;
          });
        }
      },
      error: (err) => {
        loadingMsg.loading = false;
        loadingMsg.error = 'Could not reach the reporting service. Is the backend running?';
        this.shouldScroll = true;
        this.cdr.detectChanges();
        console.error(err);
      }
    });
  }

  regenerate(session: ChatSession, assistantIndex: number): void {
    const target = session.messages[assistantIndex];
    target.loading = true;
    target.text = undefined;
    target.records = undefined;
    target.sourceNote = undefined;
    target.error = undefined;
    this.shouldScroll = true;
    this.cdr.detectChanges();

    this.queryService.regenerate(session.id).subscribe({
next: (result) => {
        target.loading = false;
        target.text = result.content || undefined;
        target.records = result.records || undefined;
        target.sourceNote = result.source_note || undefined;
        target.sources = result.sources || undefined;
        this.shouldScroll = true;
        this.cdr.detectChanges();
      },
      error: (err) => {
        target.loading = false;
        target.error = 'Could not reach the reporting service. Is the backend running?';
        this.cdr.detectChanges();
        console.error(err);
      }
    });
  }

  isLatestAssistant(session: ChatSession, index: number): boolean {
    for (let i = session.messages.length - 1; i >= 0; i--) {
      if (session.messages[i].role === 'assistant') return i === index;
    }
    return false;
  }

copyMessage(msg: DisplayMessage): void {
    if (!msg.text) return;
    navigator.clipboard.writeText(msg.text).then(() => {
      msg.copied = true;
      this.cdr.detectChanges();
      setTimeout(() => { msg.copied = false; this.cdr.detectChanges(); }, 1500);
    });
  }

exportMessageRecords(msg: DisplayMessage): void {
    // Multiple sources means the AI made more than one tool call to
    // answer (e.g. "compare June and July") -- export one sheet per
    // source rather than only the last call's records, which is all
    // the old single-records export could ever capture.
    const sources = (msg.sources && msg.sources.length ? msg.sources : null)
      ?? (msg.records && msg.records.length ? [{ function_called: 'result', records: msg.records, summary: null, source: msg.sourceNote ?? null, arguments_used: {} }] : null);
    if (!sources || !sources.length) return;

    const workbook = XLSX.utils.book_new();
    const usedNames = new Set<string>();

    sources.forEach((src, i) => {
      if (!src.records || !src.records.length) return;
      const worksheet = XLSX.utils.json_to_sheet(src.records);
      const sheetName = this.uniqueSheetName(src.function_called || `Sheet${i + 1}`, usedNames);
      XLSX.utils.book_append_sheet(workbook, worksheet, sheetName);
    });

    if (!workbook.SheetNames.length) return;

    const filename = `ask-ai-export-${new Date().toISOString().slice(0, 10)}.xlsx`;
    XLSX.writeFile(workbook, filename);
  }

  // Excel sheet names: max 31 chars, no \ / ? * [ ] characters, must be
  // unique within the workbook (two tool calls to the same function,
  // e.g. one per month being compared, would otherwise collide).
  private uniqueSheetName(raw: string, used: Set<string>): string {
    let base = raw.replace(/[\\/?*\[\]]/g, ' ').trim().slice(0, 31) || 'Sheet';
    let name = base;
    let n = 2;
    while (used.has(name)) {
      const suffix = ` (${n})`;
      name = base.slice(0, 31 - suffix.length) + suffix;
      n++;
    }
    used.add(name);
    return name;
  }

  // ---------- Inline records table ----------
  // Tool results come back as generic objects with whatever shape that
  // particular report function returns (customer lists, employee lists,
  // etc.) -- there's no per-query column spec like the dashboard tables
  // have, so columns are derived from the first record's own keys.

  readonly maxInlineRecords = 20;

  recordColumns(records: any[]): string[] {
    if (!records || !records.length) return [];
    return Object.keys(records[0]);
  }

  visibleRecords(records: any[]): any[] {
    if (!records) return [];
    return records.slice(0, this.maxInlineRecords);
  }

  formatColumnLabel(key: string): string {
    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  }

  formatCellValue(value: any): string {
    if (value === null || value === undefined || value === '') return '\u2014';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') return value.toLocaleString();
    return String(value);
  }

  // ---------- Voice input (Web Speech API) ----------

  private setupSpeechRecognition(): void {
    const SpeechRecognitionCtor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      this.speechSupported = false;
      return;
    }
    this.recognition = new SpeechRecognitionCtor();
    this.recognition!.continuous = false;
    this.recognition!.interimResults = false;
    this.recognition!.lang = 'en-US';

    this.recognition!.onresult = (event: any) => {
      const transcript = event.results?.[0]?.[0]?.transcript;
      if (transcript) {
        this.input = this.input ? `${this.input} ${transcript}` : transcript;
        this.cdr.detectChanges();
        if (this.composerInputRef) this.autoGrow(this.composerInputRef.nativeElement);
      }
    };
    this.recognition!.onerror = () => {
      this.isRecording = false;
      this.cdr.detectChanges();
    };
    this.recognition!.onend = () => {
      this.isRecording = false;
      this.cdr.detectChanges();
    };
  }

  toggleVoiceInput(): void {
    if (!this.speechSupported || !this.recognition) {
      alert('Voice input is not supported in this browser. Try Chrome or Edge.');
      return;
    }
    if (this.isRecording) {
      this.recognition.stop();
      this.isRecording = false;
    } else {
      this.recognition.start();
      this.isRecording = true;
    }
  }

  // ---------- Display helpers ----------

  private scrollToBottom(): void {
    if (this.messageListRef) {
      const el = this.messageListRef.nativeElement;
      el.scrollTop = el.scrollHeight;
    }
  }
}