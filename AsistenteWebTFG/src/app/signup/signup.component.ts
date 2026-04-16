import { Component, OnInit } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { UsuarioRegistrar } from 'src/models/usuario-registrar/usuario-registrar';
import { AuthenticationService } from 'src/services/authentication/authentication.service';

@Component({
  selector: 'app-signup',
  templateUrl: './signup.component.html',
  styleUrls: ['./signup.component.scss']
})
export class SignupComponent implements OnInit {

  usuario: UsuarioRegistrar = new UsuarioRegistrar();

  constructor(private authenticationService: AuthenticationService, private router: Router, private snackBar: MatSnackBar) { }

  ngOnInit(): void {
  }

  signup() {

    this.usuario.correo = this.usuario.correo.trim();
    this.usuario.nombre = this.usuario.correo.trim();
    this.usuario.password = this.usuario.password.trim();

    if (this.usuario.nombre.length <= 0 || this.usuario.nombre.length >= 255) { return; }
    if (this.usuario.correo.length <= 0 || this.usuario.correo.length >= 255) { return; }
    if (this.usuario.password.length <= 0 || this.usuario.password.length >= 63) { return; }

    let correo = this.usuario.correo.toLocaleLowerCase();
    if ( !correo.endsWith('upv.es') && !correo.endsWith('upv.edu.es') ) {
      this.snackBar.open('El correo electrónico debe pertenecer al dominio de upv.es o upv.edu.es', 'OK', {
        duration: 5000,
        horizontalPosition: 'center',
        verticalPosition: 'top',
      });
      return;
    }

    this.authenticationService.signup(this.usuario).subscribe(res => {
      if (res.ok) {
        this.snackBar.open(res.data, 'OK', {
          duration: 5000,
          horizontalPosition: 'center',
          verticalPosition: 'top',
        });
        this.router.navigate(['/login']);
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
