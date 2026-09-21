import { Injectable, Inject, PLATFORM_ID, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';

export interface AppConfig {
  demo_mode: boolean;
  demo_email?: string | null;
}

const LIVE_CONFIG: AppConfig = { demo_mode: false };

@Injectable({ providedIn: 'root' })
export class AppConfigService {
  private readonly apiUrl = '/api';
  readonly config = signal<AppConfig>(LIVE_CONFIG);

  constructor(
    private http: HttpClient,
    @Inject(PLATFORM_ID) platformId: object,
  ) {
    // Only the browser should ask the API; prerender/SSR has no backend.
    if (isPlatformBrowser(platformId)) {
      this.load();
    }
  }

  get demoMode(): boolean {
    return this.config().demo_mode;
  }

  get demoEmail(): string {
    return this.config().demo_email || '';
  }

  private load(): void {
    this.http.get<AppConfig>(`${this.apiUrl}/config`).subscribe({
      next: (config) => this.config.set({
        demo_mode: !!config.demo_mode,
        demo_email: config.demo_email ?? null,
      }),
      error: () => this.config.set(LIVE_CONFIG),
    });
  }
}
