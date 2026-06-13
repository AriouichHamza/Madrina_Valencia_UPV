import { AfterContentChecked, Component, ElementRef, HostListener, NgProbeToken, OnDestroy, OnInit, Query, QueryList, ViewChild, ViewChildren } from '@angular/core';
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
import { NavbarComponent } from '../navbar/navbar.component';

import { saveAs } from 'file-saver';
import { JsonPipe } from '@angular/common';
import { CalificadoAutomatizado } from 'src/models/calificado-automatizado/calificadoAutomatizado';
import { NextExamenImg } from '../next-examen-img/next-examen-img.component';
import { ExamenAutomatizado } from 'src/models/examen-automatizado/examenAutomatizado';
import { Asignatura } from 'src/models/asignatura/asignatura';

@Component({
  selector: 'app-examen-advanced',
  templateUrl: './examen-advanced.component.html',
  styleUrls: ['./examen-advanced.component.scss']
})
export class ExamenAdvancedComponent implements OnInit, AfterContentChecked {

  readonly LABEL_ALUMNO: string = 'Escriba el nombre y selecciona el alumno de la lista';
  readonly LABEL_NOTA: string = 'Nota entre 0 y 10, los decimales se aceptan con "," o "."';
  readonly LABEL_NAV: string = 'Subir (W / ↑) | Bajar (S / ↓)';
  readonly LABEL_SAVE: string = 'Pulsa "Enter" para confirmar y pasar al siguiente alumno';

  @ViewChild('imgContainer') imgContainer!: ElementRef;
  @ViewChild(MatSort) sort!: MatSort;
  // For the table and editing
  @ViewChild('examenCalificados') examenCalificados!: ElementRef;
  @ViewChild('examenCalificar') examenCalificar!: ElementRef;
  //@ViewChildren('tableRow') tableRows!: QueryList<ElementRef>;
  @ViewChildren('tableRow', { read: ElementRef }) tableRows!: QueryList<ElementRef<HTMLTableRowElement>>;
  @ViewChild('imgNextExamenComponent') imgNextExamenComponent!: NextExamenImg;

  id: number = 0;
  option: string = '';
  alumnoLabel: string = '';
  alumno: AlumnoExamen = new AlumnoExamen();
  alumnos: AlumnoExamen[] = [];
  autocompleteControl = new FormControl();
  calificados: CalificadoAutomatizado[] = [];
  calificadosSource: MatTableDataSource<CalificadoAutomatizado> = new MatTableDataSource<CalificadoAutomatizado>();
  calificadosHeader: string[] = ['dni', 'apellidos', 'nombre', 'nota', 'ini', 'fin', 'D.', 'verificado', 'edit'];
  disabledSendButton: boolean = false;
  downloadPerc: number = 0;
  edit: AlumnoExamen = new AlumnoExamen();
  examen: ExamenAutomatizado = new ExamenAutomatizado();
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

  /*
  New auxiliary variables
  */
  imgNextExamen: string = '';
  imgNextExamenHeight: number = 0;
  imgNextExamenPos: number = 1;

  loading: boolean = true;
  loadingProgress: number = 0;
  loadingState: string = '';

  selectedRow: CalificadoAutomatizado = new CalificadoAutomatizado();
  selectedElement!: HTMLElement;
  lastSelectedRow!: HTMLElement;
  verificados: number = 0;
  sinVerificar: number = 0;

  finLoadingImages: boolean = false;

  erroresPrediccion: string = '';
  intersecciones: string = '';
  discontinuidades: string = '';

  constructor(private route: ActivatedRoute, private apiService: ApiService,
    private socketService: SocketService, public dialog: MatDialog,
    private snackBar: MatSnackBar, private router: Router) {
    let id = this.route.snapshot.paramMap.get('id');
    this.id = id == null ? -1 : parseInt(id);

    this.filteredAlumnos = new Observable();
    this.setFilter();
  }

  ngOnInit(): void {


    if (!this.socketService.isConnected()) { this.socketService.connect(); }
    this.initListeners();
    this.getExamen();
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
  jsonToCalificado(c: any) {
    let calificado = new CalificadoAutomatizado();

    calificado.id = c.id;
    calificado.apellidos = c.apellidos;
    calificado.asignatura = c.asignatura;
    calificado.dni = c.dni;
    calificado.examen = c.examen;
    calificado.fin = c.fin;
    calificado.ini = c.ini;
    calificado.nombre = c.nombre;
    calificado.nota = c.nota;
    return calificado;
  }
  // For editing graded records
  editCalificado(c: CalificadoAutomatizado) {
    this.edit = new AlumnoExamen();
    this.edit.id = c.id;
    this.edit.apellidos = c.apellidos;
    this.edit.asignatura = c.asignatura;
    this.edit.dni = c.dni;
    if (c.nombre != '')
      this.edit.label = c.apellidos + ', ' + c.nombre + ' [' + c.dni + ']';
    else
      this.edit.label = "";
    this.edit.nombre = c.nombre;

    this.alumnoLabel = this.edit.label;
    this.nota = c.nota.toString();
    this.setPagIni(c.ini);
    this.setPagFin(c.fin);
    this.imgsPos = c.ini;
    // Save the row that was clicked

    this.focusElements[0].focus();
    this.selectedElement = this.focusElements[0];
  }
  editCalificadoFromButton() {
    let calificadoAux = new CalificadoAutomatizado();
    calificadoAux.ini = this.selectedRow.fin + 1;
    this.editCalificado(calificadoAux);
  }

  onRowClickEvent(event: MouseEvent, row: any) {
    this.selectedElement = event.target as HTMLElement;
    this.lastSelectedRow = this.selectedElement;
    this.onRowClick(row);
  }
  onRowClick(row: any) {

    let calificadoAux = new CalificadoAutomatizado();
    calificadoAux.id = row.id;
    calificadoAux.apellidos = row.apellidos;
    calificadoAux.asignatura = row.asignatura;
    calificadoAux.dni = row.dni;
    calificadoAux.examen = row.examen;
    calificadoAux.fin = row.fin;
    calificadoAux.ini = row.ini;
    calificadoAux.nombre = row.nombre;
    calificadoAux.nota = row.nota;
    calificadoAux.verificado = row.verificado;

    this.selectedRow = row;
    this.changeNextExamenImage(calificadoAux);
    this.showCalificadoInfo(calificadoAux);

  }
  showCalificadoInfo(c: CalificadoAutomatizado) {
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
    this.imgsPos = c.ini;
  }

  changeNextExamenImage(calificado: CalificadoAutomatizado) {
    if (calificado.fin == this.imgs.length) {
      this.imgNextExamenComponent.changeImage(this.imgs[calificado.fin - 1]);
    }
    else {
      this.imgNextExamenComponent.changeImage(this.imgs[calificado.fin]);
    }

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
    } else if (n == 0 && event.key == 'Enter') {
      this.sendCalificado();
    }
  }
  // Intercept any key press
  @HostListener('document:keydown', ['$event'])
  handleKeydown(event: KeyboardEvent) {
    //event.preventDefault();
    if (this.selectedElement != undefined && this.selectedElement.tagName == "TD" || this.selectedElement.tagName == "TR") {

      if (event.key.toUpperCase() == 'N') {
        event.preventDefault();
        console.log("Añadir nuevo alumno")
        let calificadoAux = new CalificadoAutomatizado();
        calificadoAux.ini = this.selectedRow.fin + 1;
        this.editCalificado(calificadoAux);

      }
      else
        if (event.key == 'Tab') {
          event.preventDefault();
          this.focusNextOnRow(event, this.selectedRow);
        }
        else if (event.key === 'Enter' ||
    event.key.toUpperCase() === 'E' ||
    event.code === 'Space' ||
    event.key === ' ') {
          event.preventDefault();
          console.log("Enter on Row Global")
          this.lastSelectedRow = this.selectedElement;
          this.editCalificado(this.selectedRow);
        }

    }


  }

  handleKeydownOnTable(event: KeyboardEvent) {
    event.preventDefault();
    if (event.key == 'Tab') {
      this.focusNextOnRow(event, this.selectedRow);
    }
    else if (event.key == 'Enter') {
      console.log("Enter on Row")
      this.editCalificado(this.selectedRow);
    }

  }
  focusNextOnRow(event: KeyboardEvent, row: any) {
    event.preventDefault();
    console.log("Se ha pulsado una tecla sobre row")
    if (event.key === 'Tab') {
      // Mark it as verified

      //this.focusNextRow(row);

      this.sendVerificado(row);


      this.showCalificadoInfo(row)
      this.focusNextRow(row)
      //get next row
    }

  }
  focusNextRow(row: any) {
    let nextIndex = this.calificadosSource.data.findIndex(item => item.id == row.id)
    nextIndex += 1;
    if (nextIndex >= this.calificadosSource.data.length) {
      nextIndex = 0;
    }
    //let htmlElementAux = this.tableRows.toArray();
    //htmlElementAux[nextIndex].nativeElement.scrollIntoView();
    this.tableRows.toArray()[nextIndex].nativeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    this.selectedRow = this.calificadosSource.data[nextIndex];
    this.onRowClick(this.selectedRow);
  }
  focusNextRowNotVerified() {
    this.apiService.examenAlumnosGetAutomatizado(this.examen).subscribe(res => {
      this.alumnos = <AlumnoExamen[]>res.data.alumnos;
      this.calificados = <CalificadoAutomatizado[]>res.data.calificados;
      this.updateTable();

      let index = this.calificadosSource.data.findIndex(c => c.verificado == 0);


      if (index != -1) {
        this.selectedRow = this.calificados[index];
        this.onRowClick(this.calificados[index]);
        let tableRowsArray = this.tableRows.toArray();
        let row = tableRowsArray[index];
        this.selectedElement = row.nativeElement;
        this.selectedElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });

  }

  selectText(input: HTMLInputElement) {
    setTimeout(() => {
      input.select();
    }, 0);
  }
  sendVerificado(row: any) {
    let alumno = this.getAlumnoExamen();
    let nota = this.getAlumnoNota();

    if (alumno == undefined || nota == undefined) return;

    this.disabledSendButton = true;

    let calificado = new CalificadoAutomatizado();
    calificado.id = this.edit.id;
    calificado.apellidos = alumno.apellidos;
    calificado.asignatura = alumno.asignatura;
    calificado.dni = alumno.dni;
    calificado.examen = this.examen.id;
    calificado.fin = this.pFin;
    calificado.ini = this.pIni;
    calificado.nombre = alumno.nombre;
    calificado.nota = nota;
    calificado.verificado = 1;

    if (this.edit.id > 0) {
      this.apiService.calificadoEditAutomatizado(calificado).subscribe(res => {
        this.getExamenAlumnos();
        let index = this.calificadosSource.data.findIndex(c => c.id == row.id);
        if (index != -1) {
          if (index + 1 == this.calificadosSource.data.length) { //For last row
            index = -1;
          }
          this.selectedRow = this.calificadosSource.data[index + 1];
          if (index >= this.calificadosSource.data.length)

            this.onRowClick(this.selectedRow);
        }
        this.disabledSendButton = false;
      });
    }
  }

  sendCalificado() {

    let alumno = this.getAlumnoExamen();
    let nota = this.getAlumnoNota();

    if (alumno == undefined || nota == undefined) return;

    this.disabledSendButton = true;

    let calificado = new CalificadoAutomatizado();
    calificado.id = this.edit.id;
    calificado.apellidos = alumno.apellidos;
    calificado.asignatura = alumno.asignatura;
    calificado.dni = alumno.dni;
    calificado.examen = this.examen.id;
    calificado.fin = this.pFin;
    calificado.ini = this.pIni;
    calificado.nombre = alumno.nombre;
    calificado.nota = nota;
    calificado.verificado = 1;

    if (this.edit.id > 0) {
      this.apiService.calificadoEditAutomatizado(calificado).subscribe(res => {
        this.getExamenAlumnos();
        this.disabledSendButton = false;
        this.selectedElement = this.lastSelectedRow;
        this.selectedElement.focus();
      });
    } else {
      let alumnoLabel = this.alumnoLabel.toString();
      this.apiService.calificadoNew(calificado).subscribe(res => {

        this.alumnos.splice(this.alumnos.findIndex(a => a.label == alumnoLabel), 1);
        this.setFilter();

        this.calificados.push(<CalificadoAutomatizado>res.data);
        this.updateTable();
        this.disabledSendButton = false;
      });
    }

    this.getStatistics();

    
  }

  getStatistics(){
    this.apiService.getErrorStatistics(this.examen.id).subscribe(res => {
      this.erroresPrediccion = '';
      this.intersecciones = '';
      this.discontinuidades = '';
      for (let i = 0; i < res.data.errores.length; i++) {
        this.erroresPrediccion += res.data.errores[i].fin.toString();
        if (i < res.data.errores.length - 1) {
          this.erroresPrediccion += ', ';
        }
      }
      for (let i = 0; i < res.data.intersecciones.length; i++) {
        this.intersecciones += res.data.intersecciones[i].fin.toString();
        if (i < res.data.intersecciones.length - 1) {
          this.intersecciones += ', ';
        }
      }
      for (let i = 0; i < res.data.diferencias.length; i++) {
        this.discontinuidades += res.data.diferencias[i].fin.toString();
        if (i < res.data.diferencias.length - 1) {
          this.discontinuidades += ', ';
        }
      }
    }
    );
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

  selectPageChange(value: string): void {
    this.imgsPos = parseInt(value, 10);
    if (isNaN(this.imgsPos)) { this.imgsPos = 1; }
    if (this.imgsPos < 1) { this.imgsPos = 1; }
    if (this.imgsPos > this.imgs.length) { this.imgsPos = this.imgs.length; }
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

    if (this.toggleAutoPag) { this.pFin = this.imgsPos + saltoPaginaInt - 1; }

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
        case 'fin-all': {
          if (!this.finLoadingImages) {
            this.finLoadingImages = true;
            this.focusNextRowNotVerified();
            this.getStatistics();
          }
          break;
        }
        default: this.imgs[this.imgs.length - 1] += res; break;
      }
    });

    this.socketService.selectExamenZIPFromEvent().subscribe(res => {


      if (res.done) {

        this.downloadPerc = 0;
        this.waitResponse = false;
        saveAs(environment.backend + '/' + res.url, res.filename);
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
        if (this.examen.predicted == 0) {
          this.loading = true;
          this.getExamenPrediction()
        }
        else {
          this.loading = false;
        }

        this.socketService.selectExamenImgs(paquete)
        this.getExamenAlumnosOnInit();
        this.sortBy('ini'); // Sort by page order for convenience

      }
    });
  }

  private sortBy(column: string) {
    this.calificadosSource.sort = this.sort;
    this.calificadosSource.sort.active = 'ini';
    this.calificadosSource.sort.direction = 'asc';
  }

  private getExamenPrediction() {
    this.loading = true;
    let request = {
      usuario: environment.session.id,
      asignatura: this.examen.asignatura,
      examen: this.examen.id,
      asignaturaNom: this.examen.nombre
    }


    this.socketService.insertExamenPrediction(request); // Request exam prediction

    // Wait until we receive the prediction
    this.socketService.insertExamenPredictionProcesar().subscribe(res => {

      let splittedRes = res.split(' ')

      let preamble = splittedRes[0];
      let data = splittedRes.slice(1).join(' ');

      switch (preamble) {
        case 'progress':
          let dataAux = data.split(' ')
          let progress = dataAux[0];
          let state = dataAux.slice(1).join(' ');
          this.loadingProgress = progress;
          this.loadingState = state;
          break;
        case 'done':
          this.loading = false;
          this.getExamenAlumnos();
          break;
        case 'error':
          this.loading = false;
          this.loadingState = data;
          this.snackBar.open(data, 'OK', {
            duration: 10000,
            horizontalPosition: 'center',
            verticalPosition: 'top',
          });
          break;
      }
    }
    );

  }


  private updateTable() {

    this.calificadosSource = new MatTableDataSource(this.calificados);
    this.calificadosSource.sort = this.sort;

    let pag = 0;
    this.calificados.forEach(element => { if (element.fin > pag) pag = element.fin; });
    //this.setPagIni(pag + 1);
    //this.setPagFin(this.pIni + (this.toggleAutoPag ? parseInt(this.saltoPagina) - 1 : 0));
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
  private getExamenAlumnosOnInit() {
    this.apiService.examenAlumnosGetAutomatizado(this.examen).subscribe(res => {
      this.alumnos = <AlumnoExamen[]>res.data.alumnos;
      this.calificados = <CalificadoAutomatizado[]>res.data.calificados;
      this.verificados = this.calificados.filter(c => c.verificado == 1).length;
      this.sinVerificar = this.calificados.filter(c => c.verificado == 0).length;
      this.updateTable();
    });
  }

  private getExamenAlumnos(): void {
    this.apiService.examenAlumnosGetAutomatizado(this.examen).subscribe(res => {
      this.alumnos = <AlumnoExamen[]>res.data.alumnos;
      this.calificados = <CalificadoAutomatizado[]>res.data.calificados;
      this.verificados = this.calificados.filter(c => c.verificado == 1).length;
      this.sinVerificar = this.calificados.filter(c => c.verificado == 0).length;
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
