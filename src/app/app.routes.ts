import { Routes } from '@angular/router';
import { LoginComponent } from './login/login';
import { WorkspaceComponent } from './workspace/workspace';
import { authGuard } from './auth.guard';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: '', component: WorkspaceComponent, canActivate: [authGuard] },
  { path: '**', redirectTo: '' }
];