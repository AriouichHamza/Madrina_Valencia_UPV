import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { HttpClientModule } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';

import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { FormsModule } from '@angular/forms';
import { SocketIoConfig, SocketIoModule } from 'ngx-socket-io';
import { environment } from 'src/environments/environment';

//  Angular material
import {MatAutocompleteModule} from '@angular/material/autocomplete';
import {MatButtonModule} from '@angular/material/button';
import {MatCardModule} from '@angular/material/card';
import {MatDatepickerModule} from '@angular/material/datepicker';
import {MatDialogModule} from '@angular/material/dialog';
import {MatIconModule} from '@angular/material/icon';
import {MatInputModule} from '@angular/material/input'; 
import {MatMenuModule} from '@angular/material/menu';
import {MatNativeDateModule} from '@angular/material/core';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner';
import {MatSelectModule} from '@angular/material/select';
import {MatSidenavModule} from '@angular/material/sidenav';
import {MatSlideToggleModule} from '@angular/material/slide-toggle';
import {MatSnackBarModule} from '@angular/material/snack-bar';
import {MatSortModule} from '@angular/material/sort';
import {MatTableModule} from '@angular/material/table'; 
import {MatTooltipModule} from '@angular/material/tooltip';
import {MatToolbarModule} from '@angular/material/toolbar';

//  Angular cdk
import {DragDropModule} from '@angular/cdk/drag-drop';

import { AsignaturasComponent } from './asignaturas/asignaturas.component';
import { LoginComponent } from './login/login.component';
import { EditAsignaturaComponent } from './edit-asignatura/edit-asignatura.component';
import { ButtonAsignaturaComponent } from './button-asignatura/button-asignatura.component';
import { DeleteAsignaturaComponent } from './delete-asignatura/delete-asignatura.component';
import { AddExamenComponent } from './add-examen/add-examen.component';
import { ButtonExamenComponent } from './button-examen/button-examen.component';
import { ExamenComponent } from './examen/examen.component';
import { ExamenAdvancedComponent } from './examen-advanced/examen-advanced.component';
import { NavbarComponent } from './navbar/navbar.component';
import { ImageZoomComponent } from './image-zoom/image-zoom.component';
import { DeleteExamenComponent } from './delete-examen/delete-examen.component';
import { CsvReaderComponent } from './csv-reader/csv-reader.component';
import { SignupComponent } from './signup/signup.component';
import { RecuperarPasswordComponent } from './recuperar-password/recuperar-password.component';
import { CambiarCorreoComponent } from './cambiar-correo/cambiar-correo.component';
import { PasswordComponent } from './password/password.component';
import {NextExamenImg} from './next-examen-img/next-examen-img.component';

const config: SocketIoConfig = {
  url: environment.backend,
  options: {
    transports: ['websocket'],
    autoConnect: false
  }
}

@NgModule({
  declarations: [
    AppComponent,
    AsignaturasComponent,
    LoginComponent,
    EditAsignaturaComponent,
    ButtonAsignaturaComponent,
    DeleteAsignaturaComponent,
    AddExamenComponent,
    ButtonExamenComponent,
    ExamenComponent,
    NavbarComponent,
    ImageZoomComponent,
    DeleteExamenComponent,
    CsvReaderComponent,
    SignupComponent,
    RecuperarPasswordComponent,
    CambiarCorreoComponent,
    PasswordComponent,
    ExamenAdvancedComponent,
    NextExamenImg
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    BrowserAnimationsModule,
    HttpClientModule,
    CommonModule,
    DragDropModule,
    FormsModule,
    ReactiveFormsModule,
    SocketIoModule.forRoot(config),
    MatAutocompleteModule,
    MatButtonModule,
    MatCardModule,
    MatDatepickerModule,
    MatDialogModule,
    MatIconModule,
    MatInputModule,
    MatMenuModule,
    MatNativeDateModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatSidenavModule,
    MatSlideToggleModule,
    MatSnackBarModule,
    MatTableModule,
    MatSortModule,
    MatTooltipModule,
    MatToolbarModule,
  ],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule {}
