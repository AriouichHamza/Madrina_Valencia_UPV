import { Component, OnInit } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ActivatedRoute, Router } from '@angular/router';
import { Usuario } from 'src/models/usuario/usuario';
import { AuthenticationService } from 'src/services/authentication/authentication.service';

@Component({
  selector: 'app-password',
  templateUrl: './password.component.html',
  styleUrls: ['./password.component.scss']
})
export class PasswordComponent implements OnInit {

  usuario: Usuario = new Usuario();

  password1: string = '';
  password2: string = '';

  valido: number = 0;

  constructor(private route: ActivatedRoute, private router: Router,
    private authenticationService: AuthenticationService, private snackBar: MatSnackBar) { }

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      let keys = Object.keys(params);
      if (keys.length == 2 && params['u'] != undefined && params['t'] != undefined) {
        this.authenticationService.validarCambioPass(params['u'], params['t']).subscribe(res => {
          if (res.ok) {
            this.setUsuario(res.data.id, res.data.nombre, params['t']);
            this.valido = 2;
          } else {
            this.valido = 1;    
          }
        });
      } else {
        this.valido = 1;
      }
    });
  }

  cambiar() {

    this.password1 = this.password1.trim();
    this.password2 = this.password2.trim();

    if (this.password1 != this.password2) {
      this.snackBar.open('Las contraseña deben ser las mismas', 'OK', {
        duration: 5000,
        horizontalPosition: 'center',
        verticalPosition: 'top',
      });
      return;
    }

    this.authenticationService.cambioPass(this.usuario.id, this.usuario.token, this.password1).subscribe(res => {

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

  private setUsuario(id: string, nombre: string, token: string) {
    this.usuario.id = id;
    this.usuario.nombre = nombre;
    this.usuario.token = token;
  }
}
