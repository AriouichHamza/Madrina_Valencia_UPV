import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { environment } from 'src/environments/environment';
import { Usuario } from 'src/models/usuario/usuario';

@Injectable({
  providedIn: 'root'
})
export class StorageService {

  private session: Usuario = new Usuario();

  constructor(private router: Router) {
    this.session = this.loadSession();
    environment.session = this.session;
  }

  getSession(): Usuario {
    return this.session;
  }

  isAuthenticated(): boolean {
    return (this.session.token.length > 0);
  }

  loadSession(): Usuario {
    let json = sessionStorage.getItem('session');
    return (json) ? <Usuario> JSON.parse(json) : new Usuario();
  }

  setSession(session: Usuario): void {
    this.session = session;
    environment.session = session;
    sessionStorage.setItem('session', JSON.stringify(this.session));
  }

  removeSession(): void {
    this.session = new Usuario();
    environment.session = new Usuario();
    sessionStorage.removeItem('session');
  }
}
