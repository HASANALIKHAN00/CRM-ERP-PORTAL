import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const auth = inject(AuthService);

  // withCredentials ensures the httpOnly session cookie is sent/received
  // on every API call, without needing every call site to set it manually.
  const authedReq = req.clone({ withCredentials: true });

  return next(authedReq).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && !req.url.includes('/auth/login')) {
        auth.currentUser.set(null);
        router.navigate(['/login']);
      }
      return throwError(() => err);
    })
  );
};