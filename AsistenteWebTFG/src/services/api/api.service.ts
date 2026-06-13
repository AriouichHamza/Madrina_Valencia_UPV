import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map } from 'rxjs';
import { environment } from 'src/environments/environment';
import { Response } from 'src/models/response/response';

@Injectable({
  providedIn: 'root'
})
export class ApiService {

  readonly URL: string = environment.backend + '/api';

  constructor(private http: HttpClient) { }

  asignaturas() {
    return this.sendPost('/asignaturas');
  }
  
  asignaturaEdit(asignatura:any, pref:any, deleteAlumnos:boolean) {
    let data = {
      asignatura: asignatura,
      pref: pref,
      deleteAlumnos: deleteAlumnos
    }
    return this.sendPost('/asignaturas/update', data);
  }

  asignaturaDelete(asignatura:any) {
    return this.sendPost('/asignaturas/delete', asignatura);
  }

  asignaturaNew(asignatura:any, pref:any) {
    let data = {
      asignatura: asignatura,
      pref: pref
    }
    return this.sendPost('/asignaturas/insert', data);
  }

  asignaturaGetAlumnos(asignatura:any) {
    return this.sendPost('/asignaturas/select/alumnos', asignatura);
  }

  calificadoEdit(calificado:any) {
    return this.sendPost('/calificado/update', calificado);
  }
  // Added by Jefferson
  calificadoEditAutomatizado(calificado:any){
    return this.sendPost('/calificado/update-automatizado', calificado);
  }

  calificadoNew(calificado:any) {
    return this.sendPost('/calificado/insert', calificado);
  }

  examenGet(examen:any) {
    return this.sendPost('/examen/select', examen);
  }

  examenNew(examen:any) {
    return this.sendPost('/examen/insert', examen);
  }

  examenDelete(examen:any) {
    return this.sendPost('/examen/delete', examen);
  }

  examenDownload(examen:any) {
    return this.sendPost('/examen/zip', examen);
  }

  examenEditSalto(examen: any) {
    return this.sendPost('/examen/update/saltoPag', examen);
  }

  examenAlumnosGet(examen: any) {
    return this.sendPost('/examen/alumnos/select', examen);
  }
  // Added by Jefferson
  examenAlumnosGetAutomatizado(examen:any){
    return this.sendPost('/examen/alumnos/select-automatizado', examen);
  }

  usuarioEditCorreo(correo: any) {
    return this.sendPost('/usuario/update/correo', correo);
  }

  prefGet() {
    return this.sendPost('/preferencias/select');
  }
  // Added by Jefferson
  getErrorStatistics(asignatura:any) {
    return this.sendPost('/prediction/statistics', asignatura);
  }
  
  private sendPost(path:string, data?:object) {

    //console.log('send', path);

    let body = {};
    if (data == undefined) { body = { session: environment.session }; }
    else { body = { session: environment.session, data: data }; }

    return this.http.post(this.URL + path, body).pipe( map(res => { return <Response>res; }) );
  }
}
