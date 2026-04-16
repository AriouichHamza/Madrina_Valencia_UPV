import { Component, OnInit } from '@angular/core';
import { MatDialogRef } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Response } from 'src/models/response/response';
import { ApiService } from 'src/services/api/api.service';
import { StorageService } from 'src/services/storage/storage.service';

@Component({
  selector: 'app-cambiar-correo',
  templateUrl: './cambiar-correo.component.html',
  styleUrls: ['./cambiar-correo.component.scss']
})
export class CambiarCorreoComponent implements OnInit {

  correo: string = '';

  constructor(private apiService: ApiService, private snackBar: MatSnackBar,
    public dialogRef: MatDialogRef<CambiarCorreoComponent>, private storageService: StorageService) { }

  ngOnInit(): void {
    if (!this.storageService.isAuthenticated()) {
      let res = new Response();
      res.ok = false;
      res.data = 'No hay sesión iniciada';
      res.message = 'No hay sesión iniciada';
      this.dialogRef.close(res);
    }
  }

  enviar() {

    this.correo = this.correo.trim();

    if (this.correo.length <= 0 || this.correo.length >= 255) { return; }

    let c = this.correo.toLocaleLowerCase();
    if (!c.endsWith('upv.es') && !c.endsWith('upv.edu.es')) {
      this.snackBar.open('El correo electrónico debe pertenecer al dominio de upv.es o upv.edu.es', 'OK', {
        duration: 5000,
        horizontalPosition: 'center',
        verticalPosition: 'top',
      });
      return;
    }

    this.apiService.usuarioEditCorreo(this.correo.trim()).subscribe(res => {
      if (res.ok) {
        this.dialogRef.close(res);
      } else {
        this.snackBar.open(res.message, 'OK', {
          duration: 5000,
          horizontalPosition: 'center',
          verticalPosition: 'top',
        });
      }
    });
  }
}
