import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ChatComponent } from '../chat/chat';
import { DashboardComponent } from '../dashboard/dashboard';
import { AuthService } from '../auth';
import { AppConfigService } from '../services/app-config';

@Component({
  selector: 'app-workspace',
  standalone: true,
  imports: [CommonModule, ChatComponent, DashboardComponent],
  templateUrl: './workspace.html',
  styleUrl: './workspace.scss'
})
export class WorkspaceComponent {
  activeTab: 'ask-ai' | 'dashboard' = 'ask-ai';
  dashArea: 'dashboard' | 'activity' = 'dashboard';
  profileMenuOpen = false;

  constructor(public auth: AuthService, public appConfig: AppConfigService, private router: Router) {}

  get initials(): string {
    const name = this.auth.currentUser()?.full_name || '';
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return '?';
    if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
    return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
  }

  setTab(tab: 'ask-ai' | 'dashboard'): void {
    this.activeTab = tab;
  }

  toggleProfileMenu(): void {
    this.profileMenuOpen = !this.profileMenuOpen;
  }

  closeProfileMenu(): void {
    this.profileMenuOpen = false;
  }

  logout(): void {
    this.auth.logout().subscribe(() => this.router.navigate(['/login']));
  }
}