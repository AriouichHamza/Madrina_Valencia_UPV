import { Component, OnInit } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { AuthenticationService } from 'src/services/authentication/authentication.service';
import { StorageService } from 'src/services/storage/storage.service';
import { RecuperarPasswordComponent } from '../recuperar-password/recuperar-password.component';
import { environment } from 'src/environments/environment';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss']
})
export class LoginComponent implements OnInit {

  usuario: any = { nombre: '', password: '' }
  isLoading = false;

  constructor(private authenticationService: AuthenticationService,
    private storageService: StorageService, private router: Router,
    private snackBar: MatSnackBar, public dialog: MatDialog) { }

  ngOnInit(): void {

    if (this.storageService.isAuthenticated()) {
      this.router.navigate(['/asignaturas']);
    }
  }

  cambioDePass() {
    const dialogRef = this.dialog.open(RecuperarPasswordComponent);

    dialogRef.afterClosed().subscribe(result => {

      if (result != undefined) {
        if (result.ok) {
          this.snackBar.open(result.data, 'OK', {
            duration: 5000,
            horizontalPosition: 'center',
            verticalPosition: 'top',
          });
        } else {
          this.snackBar.open(result.message, 'OK', {
            duration: 5000,
            horizontalPosition: 'center',
            verticalPosition: 'top',
          });
        }
      }
    });
  }

  signup() {
    this.router.navigate(['/sign-up']);
  }

info() {
    window.open('/info/index.html', "_blank");
  }
  
  login() {
    this.isLoading = true;
    this.authenticationService.login(this.usuario).subscribe(res => {
      this.isLoading = false;
      if (res.ok) {
        this.storageService.setSession(res.data);
        this.router.navigate(['/asignaturas']);
      } else {
        this.snackBar.open(res.message, 'OK', {
          duration: 5000,
          horizontalPosition: 'center',
          verticalPosition: 'top',
        });
      }
    }, () => {
      this.isLoading = false;
    });
  }
}
