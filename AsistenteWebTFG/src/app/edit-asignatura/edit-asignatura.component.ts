import { Component, EventEmitter, Inject, Input, OnChanges, OnInit, Output, SimpleChanges } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { Alumno } from 'src/models/alumno/alumno';
import { AsignaturaResult } from 'src/models/asignatura-result/asignatura-result';
import { Asignatura } from 'src/models/asignatura/asignatura';
import { Pref } from 'src/models/pref/pref';
import { ApiService } from 'src/services/api/api.service';

@Component({
  selector: 'app-edit-asignatura',
  templateUrl: './edit-asignatura.component.html',
  styleUrls: ['./edit-asignatura.component.scss']
})
export class EditAsignaturaComponent implements OnInit {

  asignatura: Asignatura = new Asignatura();
  curso: string = '';
  prefCSV: Pref = new Pref();

  alumnos: Alumno[] = [];

  colores: string[] = ['#ec7063', '#a569bd', '#5dade2', '#45b39d', '#58d68d', '#f5b041', '#dc7633', '#99a3a4', '#566573'];
  csvModified: boolean = false;
  errorMessage: string = '';
  waitResponse: boolean = false;

  constructor(private apiService: ApiService, @Inject(MAT_DIALOG_DATA) public data: any,
    public dialogRef: MatDialogRef<EditAsignaturaComponent>) {
    this.curso = data.curso;
    if (data.asignatura != undefined) {
      this.asignatura = data.asignatura;
    }    
  }

  ngOnInit(): void {
    
    this.alumnos = [];
    this.csvModified = false;
    this.errorMessage = '';
    this.waitResponse = false;

    if (this.asignatura == undefined || this.asignatura.id == 0) {
      this.asignatura = new Asignatura();
      this.asignatura.curso = this.curso;
      this.asignatura.color ='#ec7063';
    } else {
      this.apiService.asignaturaGetAlumnos(this.asignatura.id).subscribe(res => {
        this.alumnos = res.data;
      });
    }

    this.apiService.prefGet().subscribe((res) => {
      this.prefCSV = <Pref>res.data;
    });
  }

  editAsignatura() {

    let nombreLength = this.asignatura.nombre.trim().length;
	this.asignatura.acronimo = this.asignatura.acronimo.replace(/\s+/g, '_');
    let acronimoLength = this.asignatura.acronimo.trim().length;
    
    if (nombreLength < 1) {
      this.errorMessage = 'El campo "Nombre de la asignatura" es obligatorio';
      return;
    }

    if (nombreLength > 255) {
      this.errorMessage = 'El campo "Nombre de la asignatura" es demasiado extenso';
      return;
    }

    if (acronimoLength < 1) {
      this.errorMessage = 'El campo "Acrónimo" es obligatorio';
      return;
    }

    if (acronimoLength > 15) {
      this.errorMessage = 'El campo "Acrónimo" es demasiado extenso';
      return;
    }

    this.waitResponse = true;

    if (this.asignatura.id == 0) { this.asignaturaNew(); }
    else { this.asignaturaEdit(); }
  }

  onLoadFile() {
    this.csvModified = true;
  }

  setColor(color: string) {
    this.asignatura.color = color;
  }

  private asignaturaEdit() {

    this.apiService.asignaturaEdit(this.asignatura, this.prefCSV, this.csvModified).subscribe(res => {
      this.waitResponse = false;
      if (res.ok) {
        let result = new AsignaturaResult(res.data, this.csvModified ? this.alumnos : undefined);
        this.dialogRef.close(result);
      } else {
        this.errorMessage = (<any>res.message).sqlMessage;
      }
    });
  }

  private asignaturaNew() {

    this.apiService.asignaturaNew(this.asignatura, this.prefCSV).subscribe(res => {
      this.waitResponse = false;
      if (res.ok) {
        let result = new AsignaturaResult(res.data, this.csvModified ? this.alumnos : undefined);
        this.dialogRef.close(result);
      } else {
        this.errorMessage = (<any>res.message).sqlMessage;
      }
    });
  }
}
