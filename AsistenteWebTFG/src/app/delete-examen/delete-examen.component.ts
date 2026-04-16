import { Component, Inject, OnInit } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { ApiService } from 'src/services/api/api.service';

@Component({
  selector: 'app-delete-examen',
  templateUrl: './delete-examen.component.html',
  styleUrls: ['./delete-examen.component.scss']
})
export class DeleteExamenComponent implements OnInit {

  examen = { id: -1, asig: -1, nombre: '' }

  constructor(public dialogRef: MatDialogRef<DeleteExamenComponent>,
    @Inject(MAT_DIALOG_DATA) public data:any, private apiService: ApiService) {
      this.examen = data;
    }

  ngOnInit(): void {
  }

  delete() {
    let data = { examen: this.examen.id, asignatura: this.examen.asig }
    this.apiService.examenDelete(data).subscribe(res => {
      this.dialogRef.close(res);
    });
  }
}
