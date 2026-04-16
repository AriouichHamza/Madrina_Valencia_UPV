import { Component, OnInit, ViewChild } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatDrawerMode, MatSidenav } from '@angular/material/sidenav';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';
import { environment } from 'src/environments/environment';
import { Alumno } from 'src/models/alumno/alumno';
import { AsignaturaResult } from 'src/models/asignatura-result/asignatura-result';
import { Asignatura } from 'src/models/asignatura/asignatura';
import { CursoInfo } from 'src/models/curso-info/curso-info';
import { ExamenPaquete } from 'src/models/examen-paquete/examen-paquete';
import { ExamenProgress } from 'src/models/examen-progress/examen-progress';
import { ExamenResult } from 'src/models/examen-result/examen-result';
import { Examen } from 'src/models/examen/examen';
import { FileReaderResult } from 'src/models/file-reader-result/file-reader-result';
import { ApiService } from 'src/services/api/api.service';
import { SocketService } from 'src/services/socket/socket.service';
import { AddExamenComponent } from '../add-examen/add-examen.component';
import { DeleteAsignaturaComponent } from '../delete-asignatura/delete-asignatura.component';
import { EditAsignaturaComponent } from '../edit-asignatura/edit-asignatura.component';
import { DatePipe } from '@angular/common';
import { MatMenuModule } from '@angular/material/menu';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-asignaturas',
  templateUrl: './asignaturas.component.html',
  styleUrls: ['./asignaturas.component.scss']
})
export class AsignaturasComponent implements OnInit {

  curso: string = '';
  cursos: CursoInfo[] = [];

  loadComplete: boolean = false;

  readFilesDone:any = new Subject<FileReaderResult>();

  objectsToUpdate: any = [];
  panelForm: number = 0;

  selectedAsig: any = undefined;

  orderType: number = 0;

  constructor(private apiService: ApiService, public dialog: MatDialog,
    private snackBar: MatSnackBar, private socketService: SocketService,
    private router: Router) { }

  ngOnInit(): void {

    this.getMainInfo();
    if (!this.socketService.isConnected()) { this.socketService.connect(); }
    this.initListeners();
  }

  asignaturaDelete(asignatura: Asignatura) {

    const dialogRef = this.dialog.open(DeleteAsignaturaComponent, { data: asignatura });

    dialogRef.afterClosed().subscribe(result => {

      if (result != undefined) {
        if (result.ok) {
          this.getMainInfo();
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

  asignaturaEdit(curso: string, asignatura: Asignatura) {

    let data = {
      curso: curso,
      asignatura: Object.assign({}, asignatura)
    };

    const dialogRef = this.dialog.open(EditAsignaturaComponent, { data: data });

    dialogRef.afterClosed().subscribe(result => {
      if (result != undefined) {
        this.returnEditAsig(<AsignaturaResult>result);
      }
    });
  }

  asignaturaFilter(visible: boolean, asignatura: Asignatura, examenes: Examen[]) {
    examenes.forEach(examen => {
      if (asignatura.id != examen.asignatura) examen.visible = visible;
    })
  }

  asignaturaNew(curso: string) {

    let data = {
      curso: curso,
      asignatura: undefined
    };

    const dialogRef = this.dialog.open(EditAsignaturaComponent, { data: data });

    dialogRef.afterClosed().subscribe(result => {
      if (result != undefined) {
        this.returnEditAsig(<AsignaturaResult>result);
      }
    });
  }

  cursoNew() {
    let curso = '';
    var today = new Date();
    if (this.cursos.length == 0) {
      let year = (today.getFullYear() - 1) % 100;
	    if (today.getMonth() < 8) { curso = (year - 1) + '/' + (year);}
	     else {curso = (year) + '/' + (year+1);}
    } else {
      curso = this.cursos[0].curso;
    }
    let ano = curso.split('/')[1];
    curso = ano + '/' + (parseInt(ano) + 1);
    let cursoInfo = new CursoInfo(curso, [], []);
    this.cursos.unshift(cursoInfo);
  }

  examenNew(asignatura: Asignatura) {

    const dialogRef = this.dialog.open(AddExamenComponent, { data: asignatura });

    dialogRef.afterClosed().subscribe(result => {
      if (result != undefined) {
        this.returnAddExam(<ExamenResult>result);
      }
    });
  }

  examenOpen(examen: Examen, option: number) {
    if(option == 0) {
      this.router.navigate(['/examen', examen.id]);
    } else  if(option == 1) {
      this.router.navigate(['/examen-advanced', examen.id]);
    }
  }

  ordenar(type: number) {

    this.orderType = type;

    let funSort = (a: Examen, b: Examen) => { return 0; }

    switch (type) {
      case 1: funSort = (a, b) => { return a.fecha - b.fecha; }; break;
      case 2: funSort = (a, b) => { return b.fecha - a.fecha; }; break;
      case 3: funSort = (a, b) => { return a.nombre.localeCompare(b.nombre); }; break;
      case 4: funSort = (a, b) => { return ( a.nombre.localeCompare(b.nombre) * -1 ); }; break;
      default: return;
    }

    this.cursos.forEach(c => {
      c.examenes.sort(funSort);
    })
  }

  private initListeners() {

    this.socketService.insertAlumnoFromEvent().subscribe(res => {
      let index = 'asig' + res.asignatura;
      if (this.objectsToUpdate[index] != undefined) {
        this.objectsToUpdate[index].asig.acronimo = this.getPerc(res.i, this.objectsToUpdate[index].cant);
        if (res.i >= this.objectsToUpdate[index].cant - 1) {
          delete this.objectsToUpdate[index];
          this.getMainInfo();
        }
      }
    });

    this.socketService.insertExamenProcesar().subscribe(res => {
      let index = 'exam' + res;
      let examen = <Examen>this.objectsToUpdate[index];
      if (examen == undefined || examen.progress == undefined) return;

      examen.progress.procesar++;
    });

    this.socketService.insertExamenCrear().subscribe(res => {
      let index = 'exam' + res;
      let examen = <Examen>this.objectsToUpdate[index];
      if (examen == undefined || examen.progress == undefined) return;

      examen.progress.crear++;
    });

    this.socketService.insertExamenGenerar().subscribe(res => {
      let index = 'exam' + res.idExam;
      let examen = <Examen>this.objectsToUpdate[index];
      if (examen == undefined || examen.progress == undefined) return;

      examen.progress.generar = res.cont;
      examen.progress.generarTotal = res.total;
    });

    this.socketService.insertExamenPreparar().subscribe(res => {
      let index = 'exam' + res.idExam;
      let examen = <Examen>this.objectsToUpdate[index];
      if (examen == undefined || examen.progress == undefined) return;

      examen.progress.preparar = res.cont;
      examen.progress.prepararTotal = res.total;
    });

    this.socketService.insertExamenListo().subscribe(res => {

      let index = 'exam' + res.idExam;
      let examen = <Examen>this.objectsToUpdate[index];
      if (examen.progress != undefined) {
        let current = new Date().getTime();
        let old = examen.progress.tiempo;
        let diff = new Date(current - old);
        let msec = diff.getTime();
        let h = Math.floor(msec / 1000 / 60 / 60);
        let hh = h > 9 ? h.toString() : '0' + h;
        msec -= h * 1000 * 60 * 60;
        let m = Math.floor(msec / 1000 / 60);
        let mm = m > 9 ? m.toString() : '0' + m;
        msec -= m * 1000 * 60;
        let s = Math.floor(msec / 1000);
        let ss = s > 9 ? s.toString() : '0' + s;
        msec -= s * 1000;
        let message = `${examen.nombre} ha tadado en procesarse ${hh}:${mm}:${ss}`;
        this.snackBar.open(message, 'OK', {
          duration: 10000,
          horizontalPosition: 'center',
          verticalPosition: 'top',
        });
      }

      this.getMainInfo();

    });

    this.socketService.insertExamenError().subscribe(res => {

      let index = 'exam' + res.idExam;
      let examen = <Examen>this.objectsToUpdate[index];

      let message = ''
      if (examen == undefined || examen.progress == undefined) {
        message = res.message;
      } else {
        message = res.message + ' ' + examen.nombre;
      }

      this.snackBar.open(message, 'OK', {
        duration: 10000,
        horizontalPosition: 'center',
        verticalPosition: 'top',
      });

      this.getMainInfo();
    });


    this.readFilesDone.subscribe((result:FileReaderResult) => {

      let index = 'exam' + result.idExamen;
      let examen = <Examen>this.objectsToUpdate[index];
      if (examen.progress == undefined) return;

      if (examen.progress.tiempo == 0) examen.progress.tiempo = new Date().getTime();

      examen.progress.leer++;

      let array = this.splitString(result.binaryString);

      let idPaquete = examen.id + examen.nombre + result.order;
      let payloadNewFile = examen.nombre + result.order + '.pdf';
      let payloadFinFile = examen.nombre + '.pdf' + ':' + examen.id + examen.nombre + ':' + examen.progress.leerTotal;

      examen.progress.buffer.push(new ExamenPaquete(idPaquete, 'new-file', payloadNewFile));
      array.forEach(data => {
        examen.progress.buffer.push(new ExamenPaquete(idPaquete, '', data));
      });
      examen.progress.buffer.push(new ExamenPaquete(idPaquete, 'fin-file', payloadFinFile));

      if (examen.progress.leer == examen.progress.leerTotal) {

        examen.progress.subirTotal = examen.progress.buffer.length;
        examen.progress.procesarTotal = examen.progress.buffer.length;
        this.sendExamenes(examen);
      }
    })
  }

  private getPerc(cant: number, total: number) {
    return Math.round((cant / total) * 100) + '%';
  }

  private getMainInfo() {
    this.apiService.asignaturas().subscribe(res => {
      this.cursos = res.data;
      if (!this.loadComplete) this.loadComplete = true;
    });
  }

  private splitString(string: string): string[] {

    const length = 1024 * 256;
    let split: string[] = [];

    while (string.length > length) {
      let o = string.substring(0, length);
      let f = string.substring(length, string.length);
      split.push(o);
      string = f;
    }
    split.push(string.substring(0, string.length));

    return split;
  }

  private sendAlumnos(result: AsignaturaResult) {

    let asignatura = result.asignatura;
    let alumnos = result.alumnos;

    alumnos!.forEach((alumno: Alumno, i: number) => {
      let a = {
        apellidos: alumno.apellidos,
        asignatura: asignatura.id,
        dni: alumno.dni,
        i: i,
        nombre: alumno.nombre
      }
      this.socketService.insertAlumnoEmit(a);
      let index = 'asig' + asignatura.id;
      this.objectsToUpdate[index].asig.acronimo = this.getPerc(i, this.objectsToUpdate[index].cant);
    });
  }

  private sendExamenes(examen:Examen) {


    if (examen.progress == undefined) return;

    examen.progress.buffer.forEach(data => {
      let packet = {
        usuario: environment.session.id,
        asignatura: examen.asignatura,
        examen: examen.id,
        paquete: data
      }
      this.socketService.insertExamen(packet);
      examen.progress.subir++;
    });
  }

  private readExamenes(data: ExamenResult) {

    for(let i = 0; i < data.files.length; i++) {

      let done = this.readFilesDone;
      let id = data.examen.id;
      let index = i;

      let reader = new FileReader();
      reader.onload = () => {
        if (reader.result != null) {
          let result = new FileReaderResult();

          result.binaryString = reader.result.toString();
          result.idExamen = id;
          result.order = index;
          done.next(result);
        }
      };

      let file = data.files[i];
      reader.readAsDataURL(file);
    }
  }

  private returnAddExam(event: ExamenResult) {

    let localExamen = event.examen;

    let curso = this.cursos.find((c: CursoInfo) => c.curso == localExamen.curso);
    if (curso == undefined) {
      curso = new CursoInfo(localExamen.curso, [], []);
      this.cursos.push(curso);
    }
    curso.examenes.push(localExamen);
    let exam = curso.examenes.find((e: Examen) => e.id == localExamen.id);
    if (exam == undefined) return;

    exam.progress = new ExamenProgress();

    exam.progress.leerTotal = event.files.length;
    exam.progress.crearTotal = event.files.length;
    exam.progress.generarTotal = 1;

    let index = 'exam' + exam.id;
    this.objectsToUpdate[index] = exam;
    this.readExamenes(event);
  }

  private returnEditAsig(event: AsignaturaResult) {
    if (event.alumnos == undefined) {
      this.getMainInfo();
    } else {

      console.log(event);

      let localAsig = event.asignatura;
      let localCurso = localAsig.curso;

      let curso = this.cursos.find((c: CursoInfo) => c.curso == localCurso);
      if (curso == undefined) {
        curso = new CursoInfo(localCurso, [], []);
        this.cursos.push(curso);
      }
      let asig = localAsig;
      let asigIndex = curso.asignaturas.findIndex((a: Asignatura) => a.id == localAsig.id);
      if (asigIndex == -1) {
        curso.asignaturas.push(localAsig);
      } else {
        curso.asignaturas[asigIndex] = localAsig;
      }

      let index = 'asig' + asig.id;
      this.objectsToUpdate[index] = {
        asig: asig,
        cant: event.alumnos.length
      };
      this.sendAlumnos(event);
    }
  }
}
