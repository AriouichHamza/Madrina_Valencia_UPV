import { Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges } from '@angular/core';
import { MatSlideToggleChange } from '@angular/material/slide-toggle';
import { MatTableDataSource } from '@angular/material/table';
import { Alumno } from 'src/models/alumno/alumno';
import { Pref } from 'src/models/pref/pref';

export class ValueLabel {
  value: number;
  label: string;
  constructor(value: number, label: string) {
    this.value = value;
    this.label = label;
  }
}

@Component({
  selector: 'app-csv-reader',
  templateUrl: './csv-reader.component.html',
  styleUrls: ['./csv-reader.component.scss']
})
export class CsvReaderComponent implements OnChanges {

  @Input() alumnos: Alumno[] = [];
  @Output() alumnosChange = new EventEmitter<Alumno[]>();
  
  @Input() pref: Pref = new Pref();
  @Output() prefChange = new EventEmitter<Pref>();

  @Output() loadFile = new EventEmitter();

  alumnosHeader: string[] = [ 'dni', 'apellidos', 'nombre' ];
  alumnosTable = new MatTableDataSource<Alumno>();
  file: any = undefined;
  plainText: string = '';
  
  selectColumns = { dni: -1, apellido1: -1, apellido2: -1, nombre: -1 };
  selectOptions: ValueLabel[] = [];

  constructor() { }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['alumnos'] != undefined) {
      this.alumnosChange.emit(this.alumnos);
      this.alumnosTable.data = this.alumnos;
    }
  }

  onChangeHeader(event: MatSlideToggleChange) {
    this.pref.cabecera = event.checked;
    this.refreshTable();
  }

  onChangeUploadCSV(event: any) {
    this.file = event.files[0];
    this.readCSV();
    this.loadFile.emit();
  }

  refreshTable() {

    if (this.plainText.length == 0 || this.plainText == 'Archivo vacío') return;

    let lines = this.plainText.split('\n');

    this.selectOptions = [];
    if (lines.length > 0) {
      if (this.pref.cabecera) {
        lines[0].split(this.pref.sep).forEach((column, index) => {
          this.selectOptions.push( new ValueLabel(index, column) );
        });
        lines.shift();
      } else {
        lines[0].split(this.pref.sep).forEach((column, index) => {
          this.selectOptions.push( new ValueLabel(index, 'Columna ' + (index + 1)) );
        });
      }
    }

    this.alumnos = [];
    lines.forEach(line => {
      let alumnoInfo = line.split(this.pref.sep);
      if (alumnoInfo.length == this.selectOptions.length) {
        let alumno = this.splitLineToAlumno(alumnoInfo);
        if (alumno != undefined) this.alumnos.push(alumno);
      }
    });
    this.alumnosChange.emit(this.alumnos);
    this.alumnosTable.data = this.alumnos;
  }
  
  readCSV(): void {

    if (this.file == undefined) return;

    let fileReader = new FileReader();
    fileReader.onload = (e) => {
      let dataCSV = fileReader.result;
      if (dataCSV != null) {
        this.plainText = (<string>dataCSV).trim();
      } else {
        this.plainText = 'Archivo vacío';
      }
      this.refreshTable();
    }
    //https://stackoverflow.com/questions/40790042/filereader-which-encodings-are-supported
    fileReader.readAsText(this.file, this.pref.encode);
  }

  private splitLineToAlumno(line: string[]): Alumno | undefined {

    let alumno = new Alumno();
    let dni = this.selectOptions.find(o => o.value == this.selectColumns.dni);
    let apellido1 = this.selectOptions.find(o => o.value == this.selectColumns.apellido1);
    let apellido2 = this.selectOptions.find(o => o.value == this.selectColumns.apellido2);
    let nombre = this.selectOptions.find(o => o.value == this.selectColumns.nombre);

    if (dni == undefined && apellido1 == undefined && apellido2 == undefined && nombre == undefined) return undefined;

    if (dni != undefined) {
      alumno.dni = line[dni.value]
    }

    if (apellido1 != undefined && apellido2 != undefined && nombre != undefined
      && apellido1.value == apellido2.value && apellido2.value == nombre.value) {

      let splitNombre = line[apellido1.value].split(',');

      if (splitNombre.length == 1) {
        alumno.nombre = splitNombre[0].trim();
      } else if (splitNombre.length == 2) {
        alumno.apellidos = splitNombre[0].trim();
        alumno.nombre = splitNombre[1].trim();
      }
        
    } else {

      if (apellido1 != undefined && apellido2 != undefined) {

        alumno.apellidos = line[apellido1.value];
  
        if (apellido1.value != apellido2.value) {
          alumno.apellidos += ' ' + line[apellido2.value];
        }
      } else if (apellido1 != undefined) {
        alumno.apellidos = line[apellido1.value]
      } else if (apellido2 != undefined) {
        alumno.apellidos = line[apellido2.value]
      }
  
      if (nombre != undefined) {
        alumno.nombre = line[nombre.value]
      }
    }

    return alumno;
  }
}
