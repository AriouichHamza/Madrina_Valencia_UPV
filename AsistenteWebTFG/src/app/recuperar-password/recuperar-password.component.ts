import { Component, OnInit } from '@angular/core';
import { MatDialogRef } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AuthenticationService } from 'src/services/authentication/authentication.service';

@Component({
  selector: 'app-recuperar-password',
  templateUrl: './recuperar-password.component.html',
  styleUrls: ['./recuperar-password.component.scss']
})
export class RecuperarPasswordComponent implements OnInit {

  correo: string = '';

  constructor(private snackBar: MatSnackBar, private authenticationService : AuthenticationService,
    public dialogRef: MatDialogRef<RecuperarPasswordComponent>) { }

  ngOnInit(): void {

  }

  enviar() {

    this.correo = this.correo.trim();
    if (this.correo.length <= 0 || this.correo.length >= 255) { return; }

    this.authenticationService.solicitarCambioPass(this.correo).subscribe(res => {
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
