import { Component, Input, OnInit } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { environment } from 'src/environments/environment';
import { AuthenticationService } from 'src/services/authentication/authentication.service';
import { SocketService } from 'src/services/socket/socket.service';
import { StorageService } from 'src/services/storage/storage.service';
import { CambiarCorreoComponent } from '../cambiar-correo/cambiar-correo.component';

@Component({
  selector: 'app-navbar',
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.scss']
})
export class NavbarComponent implements OnInit {

  @Input() back: boolean = false;
  @Input() settings: boolean = false;

  constructor(private router: Router, private storageService: StorageService,
    private authenticationService: AuthenticationService, private socketService: SocketService,
    private snackBar: MatSnackBar, public dialog: MatDialog) { }

  ngOnInit(): void {
  }

  correo() {
    const dialogRef = this.dialog.open(CambiarCorreoComponent);

    dialogRef.afterClosed().subscribe(result => {
      if (result != undefined) {
        this.snackBar.open(result.data, 'OK', {
          duration: 5000,
          horizontalPosition: 'center',
          verticalPosition: 'top',
        });
      }
    });
  }

  info() {
    window.open(environment.backend + '/info', "_blank");
  }

  logout() {
    if (this.storageService.isAuthenticated()) {
      this.authenticationService.logout(environment.session).subscribe(res => {});
    }
    this.socketService.disconnect();
    this.storageService.removeSession();
    this.router.navigate(['/login']);
  }

  onBack() {
    this.router.navigate(['/asignaturas']);
  }

}
