import { Component, Inject, OnInit } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { ApiService } from 'src/services/api/api.service';

@Component({
  selector: 'app-delete-asignatura',
  templateUrl: './delete-asignatura.component.html',
  styleUrls: ['./delete-asignatura.component.scss']
})
export class DeleteAsignaturaComponent implements OnInit {

  asignatura: any = {
    id: -1,
    nombre: ''
  }

  constructor(public dialogRef: MatDialogRef<DeleteAsignaturaComponent>,
    @Inject(MAT_DIALOG_DATA) public data:any, private apiService: ApiService) {
      this.asignatura = data;
    }

  ngOnInit(): void {
  }

  delete() {
    this.apiService.asignaturaDelete(this.asignatura.id).subscribe(res => {
      this.dialogRef.close(res);
    });
  }
}
