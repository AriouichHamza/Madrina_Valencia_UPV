import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { environment } from 'src/environments/environment';
import { Response } from 'src/models/response/response';

@Injectable({
  providedIn: 'root'
})
export class AuthenticationService {

  readonly URL: string = environment.backend + '/login';

  constructor(private http: HttpClient) { }

  login(user: any): Observable<Response> {
    return this.http.post(this.URL + '/select', user).pipe( map(res => { return <Response>res; }) );
  }

  logout(user: any): Observable<Response> {
    return this.http.post(this.URL + '/delete', user).pipe( map(res => { return <Response>res; }) );
  }

  signup(user: any): Observable<Response> {
    return this.http.post(this.URL + '/insert', user).pipe( map(res => { return <Response>res; }) );
  }

  cambioPass(usuario: string, token: string, password: string): Observable<Response> {
    let data = { usuario: usuario, token: token, password: password }
    return this.http.post(this.URL + '/password/update', data).pipe( map(res => { return <Response>res; }) );
  }

  validarCambioPass(usuario: string, token: string): Observable<Response> {
    let data = { usuario: usuario, token: token }
    return this.http.post(this.URL + '/correo/select', data).pipe( map(res => { return <Response>res; }) );
  }

  solicitarCambioPass(correo: string): Observable<Response> {
    let data = { correo: correo };
    return this.http.post(this.URL + '/correo/insert', data).pipe( map(res => { return <Response>res; }) );
  }
}
