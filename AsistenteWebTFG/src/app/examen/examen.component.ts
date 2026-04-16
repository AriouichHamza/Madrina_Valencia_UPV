import { AfterContentChecked, Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { FormControl } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatDrawerMode, MatSidenav } from '@angular/material/sidenav';
import { MatSlideToggleChange } from '@angular/material/slide-toggle';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatSort } from '@angular/material/sort';
import { MatTable, MatTableDataSource } from '@angular/material/table';
import { ActivatedRoute, Router } from '@angular/router';
import { elementAt, map, Observable, startWith, Subscription } from 'rxjs';
import { environment } from 'src/environments/environment';
import { AlumnoExamen } from 'src/models/alumno-examen/alumno-examen';
import { Calificado } from 'src/models/calificado/calificado';
import { Examen } from 'src/models/examen/examen';
import { ApiService } from 'src/services/api/api.service';
import { SocketService } from 'src/services/socket/socket.service';
import { DeleteExamenComponent } from '../delete-examen/delete-examen.component';

import { saveAs } from 'file-saver';

@Component({
  selector: 'app-examen',
  templateUrl: './examen.component.html',
  styleUrls: ['./examen.component.scss']
})
export class ExamenComponent implements OnInit, AfterContentChecked {

  readonly LABEL_ALUMNO: string = 'Escriba el nombre y selecciona el alumno de la lista';
  readonly LABEL_NOTA: string = 'Nota entre 0 y 10, los decimales se aceptan con "," o "."';
  readonly LABEL_NAV: string = 'Subir (W / ↑) | Bajar (S / ↓)';
  readonly LABEL_SAVE: string = 'Pulsa "Enter" para confirmar y pasar al siguiente alumno';

  @ViewChild('imgContainer') imgContainer!: ElementRef;
  @ViewChild(MatSort) sort!: MatSort;

  id: number = 0;
  option: string = '';
  alumnoLabel: string = '';
  alumno: AlumnoExamen = new AlumnoExamen();
  alumnos: AlumnoExamen[] = [];
  autocompleteControl = new FormControl();
  calificados: Calificado[] = [];
  calificadosSource: MatTableDataSource<Calificado> = new MatTableDataSource<Calificado>();
  calificadosHeader: string[] = ['dni', 'apellidos', 'nombre', 'nota', 'ini', 'fin', 'edit'];
  disabledSendButton: boolean = false;
  downloadPerc: number = 0;
  edit: AlumnoExamen = new AlumnoExamen();
  examen: Examen = new Examen();
  examenTableHeight: string = '0px';
  errorCalificar: string = '';
  errorConfig: string = '';
  filteredAlumnos: Observable<string[]>;
  focusElements: HTMLElement[] = [];
  imgs: string[] = [];
  imgsPos: number = 1;
  imgHeight: number = 0;
  imgZoom: any = undefined;
  nota: string = '';
  pFin: number = 1;
  pIni: number = 1;
  tableHeight: string = '0px';
  toggleAutoPag: boolean = false;
  saltoPagina: string = '0';
  waitResponse: boolean = false;

  cuenta: number = 0;
  cuenta2: number = 0;
  cuenta_string: string = '';
  // escolta: Subscription;

  constructor(private route: ActivatedRoute, private apiService: ApiService,
    private socketService: SocketService, public dialog: MatDialog,
    private snackBar: MatSnackBar, private router: Router) {
    let id = this.route.snapshot.paramMap.get('id');
    this.id = id == null ? -1 : parseInt(id);

    this.filteredAlumnos = new Observable();
    this.setFilter();
  }

  ngOnInit(): void {
    this.getExamen();
    if (!this.socketService.isConnected()) { this.socketService.connect(); }
    this.initListeners();
  }


  ngAfterContentChecked(): void {
    if (this.imgContainer != undefined && this.imgHeight == 0) {
      this.imgHeight = this.imgContainer.nativeElement.clientHeight;
      let controlHeader = document.getElementById('controlHeader');
      let controlFooter = document.getElementById('controlFooter');
      if (controlHeader != null && controlFooter != null) {
        this.tableHeight = (this.imgHeight - controlHeader.clientHeight - controlFooter.clientHeight - 64) + 'px';
      }
    }

    let controlNombre = document.getElementById('controlNombre');
    let controlNota = document.getElementById('controlNota');
    let controlNav = document.getElementById('controlNav');
    let controlSave = document.getElementById('controlSave');

    if (this.focusElements.length == 0 &&
      controlNombre != null && controlNota != null &&
      controlNav != null && controlSave != null) {
      this.focusElements.push(controlNombre);
      this.focusElements.push(controlNota);
      this.focusElements.push(controlNav);
      this.focusElements.push(controlSave);
    }
  }

  editCalificado(c: Calificado) {
    this.edit = new AlumnoExamen();
    this.edit.id = c.id;
    this.edit.apellidos = c.apellidos;
    this.edit.asignatura = c.asignatura;
    this.edit.dni = c.dni;
    this.edit.label = c.apellidos + ', ' + c.nombre + ' [' + c.dni + ']';
    this.edit.nombre = c.nombre;

    this.alumnoLabel = this.edit.label;
    this.nota = c.nota.toString();
    this.setPagIni(c.ini);
    this.setPagFin(c.fin);
    this.imgsPos =c.ini;

    this.focusElements[0].focus();
  }

  examenDelete() {
    let data = {
      id: this.examen.id,
      asig: this.examen.asignatura,
      nombre: this.examen.nombre
    }
    const dialogRef = this.dialog.open(DeleteExamenComponent, { data: data });

    dialogRef.afterClosed().subscribe(result => {

      if (result != undefined) {
        if (result.ok) {
          this.router.navigate(['/asignaturas']);
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

  pdfUp() {
    if (this.imgsPos > 1) { this.imgsPos--; }
  }

  pdfDown() {
    if (this.imgsPos < this.imgs.length) { this.imgsPos++; }
  }

  pdfFinDown() {
    this.pdfDown();
    this.pFin = this.imgsPos;
  }

  focusNext(event: KeyboardEvent, n: number) {

    if (event.key == 'Tab') {
      event.preventDefault();
      this.focusElements[n].focus();
    } else if (n == 3) {
      if (event.key == 's' || event.key == 'ArrowDown' || event.key == 'Enter') { this.pdfDown(); }
      else if (event.key == 'w' || event.key == 'ArrowUp') { this.pdfUp(); }
      this.pFin = this.imgsPos;
    } else if (n == 0 && event.key == 'Enter') { this.sendCalificado(); }
  }

  sendCalificado() {

    let alumno = this.getAlumnoExamen();
    let nota = this.getAlumnoNota();

    if (alumno == undefined || nota == undefined) return;

    this.disabledSendButton = true;

    let calificado = new Calificado();
    calificado.id = this.edit.id;
    calificado.apellidos = alumno.apellidos;
    calificado.asignatura = alumno.asignatura;
    calificado.dni = alumno.dni;
    calificado.examen = this.examen.id;
    calificado.fin = this.pFin;
    calificado.ini = this.pIni;
    calificado.nombre = alumno.nombre;
    calificado.nota = nota;

    if (this.edit.id > 0) {
      this.apiService.calificadoEdit(calificado).subscribe(res => {
        this.getExamenAlumnos();
        this.disabledSendButton = false;
      });
    } else {
      let alumnoLabel = this.alumnoLabel.toString();
      this.apiService.calificadoNew(calificado).subscribe(res => {

        this.alumnos.splice(this.alumnos.findIndex(a => a.label == alumnoLabel), 1);
        this.setFilter();

        this.calificados.push(<Calificado>res.data);
        this.updateTable();

        this.disabledSendButton = false;
      });
    }

    this.edit = new AlumnoExamen();
    this.alumnoLabel = '';
    this.alumno = new AlumnoExamen();
    this.nota = '';
    this.focusElements[0].focus();
  }

  setPagIni(pag: number) {
    if (pag < 1) this.pIni = 1;
    else if (pag > this.imgs.length) this.pIni = this.imgs.length;
    else this.pIni = pag;
  }

  setPagFin(pag: number) {
    if (pag < 1) this.pFin = 1;
    else if (pag > this.imgs.length) this.pFin = this.imgs.length;
    else this.pFin = pag;
  }

  selectPageChange (value: string): void {
   this.imgsPos = parseInt(value, 10);
   if (isNaN(this.imgsPos)) { this.imgsPos = 1;}
   if (this.imgsPos < 1) { this.imgsPos = 1;}
   if (this.imgsPos > this.imgs.length) {this.imgsPos = this.imgs.length;}
/*   if (isNaN(parseInt(value, 10))) { this.imgsPos = 1;}
   if (parseInt(value, 10) < 1) { this.imgsPos = 1;}
   if (parseInt(value, 10) > this.imgs.length) {this.imgsPos = this.imgs.length;}
   */
}

  toggleChange(event: MatSlideToggleChange) {
    let saltoPaginaInt = parseInt(this.saltoPagina);
    this.toggleAutoPag = event.checked;

    if (isNaN(saltoPaginaInt)) {
      this.saltoPagina = '0';
      saltoPaginaInt = 0;
    }

        if (this.toggleAutoPag) { this.pFin = this.imgsPos + saltoPaginaInt-1; }

    let examen = { examen: this.examen.id, saltoPag: saltoPaginaInt, saltoPagActivo: this.toggleAutoPag };
    this.apiService.examenEditSalto(examen).subscribe(res => { });
  }

  requestZIP() {


    if (!this.waitResponse) {
      this.waitResponse = true;
      this.cuenta2++;
      let data = {
        usuario: environment.session.id,
        asignatura: this.examen.asignatura,
        examen: this.examen.id
      }
      this.socketService.selectExamenZIP(data);
    }
  }

  private initListeners() {



    this.socketService.selectExamenImgsFromEvent().subscribe(res => {
      switch (res) {
        case 'new-img': this.imgs.push(''); break;
        case 'fin-imgs': this.updateTable(); break;
        default: this.imgs[this.imgs.length - 1] += res; break;
      }
    });

    this.socketService.selectExamenZIPFromEvent().subscribe(res => {

/*		this.cuenta++;
		this.cuenta_string = this.cuenta_string + " " + this.cuenta.toString() + this.cuenta2.toString() + " " + res.done + "\n";
   	this.cuenta_string = this.cuenta_string + " " + environment.backend + '/' + res.url;
    this.snackBar.open(this.cuenta_string, 'OK', {
          //duration: 5000,
          horizontalPosition: 'center',
				verticalPosition: 'bottom',});
*/

      if (res.done) {

        this.downloadPerc = 0;
		    this.waitResponse = false;
        saveAs( environment.backend + '/' + res.url , res.filename);
//        this.escolta.unsubscribe();
      } else {
        this.downloadPerc = res.perc;
      }
    });
  }

  private getExamen() {

    this.apiService.examenGet(this.id).subscribe(res => {
      if (res.ok) {
        this.examen = res.data;
        this.saltoPagina = this.examen.saltoPag.toString();
        this.toggleAutoPag = this.examen.saltoPagActivo;

        let paquete = {
          usuario: environment.session.id,
          asignatura: this.examen.asignatura,
          examen: this.examen.id
        }

        this.socketService.selectExamenImgs(paquete);
        this.getExamenAlumnos();
      }
    });
  }

  private updateTable() {

    this.calificadosSource = new MatTableDataSource(this.calificados);
    this.calificadosSource.sort = this.sort;

    let pag = 0;
    this.calificados.forEach(element => { if (element.fin > pag) pag = element.fin; });
    this.setPagIni(pag + 1);
    this.setPagFin(this.pIni + (this.toggleAutoPag ? parseInt(this.saltoPagina) -1 : 0));
    this.imgsPos = this.pIni;
  }

  private getAlumnoExamen(): AlumnoExamen | undefined {

    let alumno = undefined;
    this.errorCalificar = '';

    if (this.alumnoLabel.trim() == '') {
      alumno = new AlumnoExamen();
      alumno.id = this.edit.id;
      return alumno;
    }

    if (this.edit.label == this.alumnoLabel) {
      alumno = this.edit;
      return alumno;
    }

    alumno = this.alumnos.find(a => a.label == this.alumnoLabel);

    if (alumno == undefined) { this.errorCalificar = 'Alumno no seleccionado'; }

    return alumno;
  }

  private getAlumnoNota(): number | undefined {

    let nota = this.nota.length == 0 ? -1 : parseFloat(this.nota.replace(',', '.'));
    this.errorCalificar = '';

    if (isNaN(nota)) {
      this.errorCalificar = 'Error en el formato de la nota';
      return undefined;
    }

    if ((nota > 10 || nota < 0) && nota != -1) {
      this.errorCalificar = 'Nota fuera de rango';
      return undefined;
    }

    return Math.round(nota * 100) / 100;
  }

  private getExamenAlumnos(): void {
    this.apiService.examenAlumnosGet(this.examen).subscribe(res => {
      this.alumnos = <AlumnoExamen[]>res.data.alumnos;
      this.calificados = <Calificado[]>res.data.calificados;
      this.updateTable();
    });
  }

  private setFilter(): void {
    this.filteredAlumnos = this.autocompleteControl.valueChanges.pipe(
      startWith(''),
      map(value => this._filter(value)),
    );
  }

  private _filter(value: string): string[] {
 /*   const filterValue = value.toLowerCase();*/
    const filterValue = value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    let alumnos = this.alumnos.filter((alumno) => {
      return alumno.label.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().includes(filterValue)
    });

    return alumnos.map(alumno => alumno.label);
  }
}
