import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap, catchError, of, map } from 'rxjs';

export interface CurrentUser {
  email: string;
  role: string;
  full_name: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private apiUrl = '/api';

  // null = not checked yet / logged out. Set on successful login or /auth/me.
  currentUser = signal<CurrentUser | null>(null);

  constructor(private http: HttpClient) {}

  login(email: string, password: string): Observable<CurrentUser> {
    return this.http
      .post<CurrentUser>(`${this.apiUrl}/auth/login`, { email, password }, { withCredentials: true })
      .pipe(tap((user) => this.currentUser.set(user)));
  }

  logout(): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/auth/logout`, {}, { withCredentials: true }).pipe(
      tap(() => this.currentUser.set(null))
    );
  }

  /**
   * Asks the backend "am I logged in, and as who" via the httpOnly cookie.
   * Used on app load / route guard, since there's no token in JS to inspect.
   */
  checkSession(): Observable<boolean> {
    return this.http.get<CurrentUser>(`${this.apiUrl}/auth/me`, { withCredentials: true }).pipe(
      map((user) => {
        this.currentUser.set(user);
        return true;
      }),
      catchError(() => {
        this.currentUser.set(null);
        return of(false);
      })
    );
  }

  isLoggedIn(): boolean {
    return this.currentUser() !== null;
  }
}