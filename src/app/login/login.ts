import { Component, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../auth';
import { AppConfigService } from '../services/app-config';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.html',
  styleUrl: './login.scss'
})
export class LoginComponent {
  email = '';
  password = '';
  error = '';
  loading = false;

  constructor(private auth: AuthService, public appConfig: AppConfigService, private router: Router) {
    effect(() => {
      const email = this.appConfig.demoEmail;
      if (email && !this.email) {
        this.email = email;
      }
    });
  }

  submit(): void {
    if (!this.email || !this.password) return;
    this.loading = true;
    this.error = '';

    this.auth.login(this.email, this.password).subscribe({
      next: () => {
        this.loading = false;
        this.router.navigate(['/']);
      },
      error: () => {
        this.loading = false;
        this.error = 'Invalid email or password.';
      }
    });
  }
}