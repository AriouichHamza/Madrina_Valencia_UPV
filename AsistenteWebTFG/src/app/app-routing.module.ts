import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { AuthorizedGuardGuard } from 'src/services/authorized-guard/authorized-guard.guard';
import { AsignaturasComponent } from './asignaturas/asignaturas.component';
import { ExamenComponent } from './examen/examen.component';
import { LoginComponent } from './login/login.component';
import { PasswordComponent } from './password/password.component';
import { SignupComponent } from './signup/signup.component';
import { ExamenAdvancedComponent } from './examen-advanced/examen-advanced.component';

const FULL = 'full';
const AUTH = [ AuthorizedGuardGuard ];
 
const routes: Routes = [
  { path: 'asignaturas', component: AsignaturasComponent, canActivate: AUTH, pathMatch: FULL },
  { path: 'examen/:id', component: ExamenComponent, canActivate: AUTH, pathMatch: FULL },
  {path: 'examen-advanced/:id', component: ExamenAdvancedComponent, canActivate: AUTH, pathMatch: FULL},
  { path: 'login', component: LoginComponent },
  { path: 'password', component: PasswordComponent },
  { path: 'sign-up', component: SignupComponent },
  { path: '', redirectTo: '/login', pathMatch: FULL},
  { path: '**', redirectTo: '/login' }
];

@NgModule({
  imports: [RouterModule.forRoot(routes, { useHash: true })],
  exports: [RouterModule]
})
export class AppRoutingModule { }
