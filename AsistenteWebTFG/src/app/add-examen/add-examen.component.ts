import { CdkDragDrop, moveItemInArray } from '@angular/cdk/drag-drop';
import { Component, EventEmitter, Inject, Input, OnInit, Output } from '@angular/core';
import { MatDatepickerInputEvent } from '@angular/material/datepicker';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { Asignatura } from 'src/models/asignatura/asignatura';
import { ExamenAutomatizado } from 'src/models/examen-automatizado/examenAutomatizado';
import { ExamenResult } from 'src/models/examen-result/examen-result';
import { FilePosition } from 'src/models/examen-result/file-position';
import { Examen } from 'src/models/examen/examen';
import { ApiService } from 'src/services/api/api.service';

@Component({
  selector: 'app-add-examen',
  templateUrl: './add-examen.component.html',
  styleUrls: ['./add-examen.component.scss']
})
export class AddExamenComponent implements OnInit {

  asignatura: Asignatura = new Asignatura();
  errorMessage: string = '';
  examen: ExamenAutomatizado = new ExamenAutomatizado();
  files: any[] = [];
  filesOrder: FilePosition[] = [];
  waitResponse: boolean = false;

  constructor(private apiService: ApiService, @Inject(MAT_DIALOG_DATA) public data: any,
    public dialogRef: MatDialogRef<AddExamenComponent>) {
    this.asignatura = data;
    this.examen.asignatura = this.asignatura.id;
  }

  ngOnInit(): void {
  }

  dateInput(event: MatDatepickerInputEvent<Date>) {
    this.examen.fecha = event.value == null ? 0 : event.value.getTime();
  }

  drop(event: CdkDragDrop<any[]>) {
    moveItemInArray(this.filesOrder, event.previousIndex, event.currentIndex);
  }

  onChangeUploadExamenes(event: any) {
    this.files = event.files;
    this.filesOrder = [];

    for (let i = 0; i < this.files.length; i++ ) {
      let file = this.files[i];
      this.filesOrder.push(new FilePosition(i, file.name));
    }
  }
  onChangeSlideAutomatizado(event: any) {
    this.examen.isAvanzado = event.checked? 1 : 0;
  }
  saveExamen() {

    this.examen.nombre = this.examen.nombre.replace(/\s+/g, '_');
	
    let nombre = this.examen.nombre.trim().length;
    if (nombre < 1 || nombre > 255) {
      this.errorMessage = 'Compruebe el nombre del examen';
      return;
    }
    if (this.examen.fecha == 0) {
      this.errorMessage = 'La fecha del examen no es válida';
      return;
    }
    if (this.files.length == 0) {
      this.errorMessage = 'No se puede crear un examen si no están los exámenes';
      return;
    }

    this.examen.asignatura = this.asignatura.id;

    this.apiService.examenNew(this.examen).subscribe(res => {
      if (res.ok) {
        let result = new ExamenResult(<Examen>res.data, this.files, this.filesOrder);
        this.dialogRef.close(result);
      } else {
        this.errorMessage = res.message;
      }
    });
  }
}
