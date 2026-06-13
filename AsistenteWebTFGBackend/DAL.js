const conexionDB = require('./connection');
const validator = require('validator');

// Strip SQL-dangerous characters and escape single quotes for safe interpolation.
function sanitizeString(str){
  str = str.replace(/[|\\]/g, '');
  str = str.replace(/'/g, "''");
  return validator.escape(str);
}

// Returns all students enrolled in the given subject.
async function getAlumnosFromAsignatura(asignatura) {
  let sql = 'SELECT * FROM alumnos WHERE asignatura = ?';
  let asignaturaInt = validator.toInt(asignatura+ "");
  let args = [asignaturaInt];
  return new Promise((resolve, reject) => {
    conexionDB.query(sql, args, (er, result, fields) => {
      if (er) {
        reject(er);
        return;
      }
      resolve(result);
    });
  });
}

// Returns all graded entries for an exam, sorted by start page ascending.
async function getCalificadosOrderByIni(examen) {
  let sql = 'SELECT * FROM calificados WHERE examen = ? ORDER BY ini';
  let examenInt = validator.toInt(examen+ "");
  let args = [examenInt];
  return new Promise((resolve, reject) => {
    conexionDB.query(sql, args, (er, result, fields) => {
      if (er){
        console.log("Query error", er);
        reject(er);
      }
      resolve(result);
    });
  });
}

// Returns students from a subject who have no graded entry in a given exam.
async function getAlumnosNoCalificados(asignatura, examen){
  let sql = 'SELECT * FROM alumnos WHERE asignatura = ? AND dni NOT IN (SELECT dni FROM calificados WHERE examen = ?)';
  let asignaturaInt = validator.toInt(asignatura+ "");
  let examenInt = validator.toInt(examen+ "");
  let args = [asignaturaInt, examenInt];
  return new Promise((resolve, reject) => {
    conexionDB.query(sql, args, (er, result, fields) => {
      if (er) {
        console.log(er);
        throw reject(er);}
      resolve(result);
    });
  });
}

// Inserts a graded copy into calificados. The verified flag is set by the caller.
async function insertAlumnoCalificado(alumno, verificado){
  let examen = parseInt(alumno.examen+ "");
  let ini = validator.toInt(alumno.ini+ "");
  let fin = validator.toInt(alumno.fin+ "");
  let nota = validator.toFloat(alumno.nota+ "");
  let verficiadoInt = verificado ? 1 : 0;

  let sql = 'INSERT INTO calificados (nombre, apellidos, dni, examen, ini, fin, nota, verificado)VALUES(?,?,? ,?,?, ?, ?,?)'
  let args = [alumno.nombre, alumno.apellidos, alumno.dni, examen, ini,fin, nota, verficiadoInt];
  return new Promise((resolve, reject) => {
    conexionDB.query(sql, args, (er, result, fields) => {
      if (er) {
        reject(er);
        return;
      }
      resolve(result);
    });
  });
}

// Updates the exam's predicted flag in the database.
async function setExamenIsPredicted(examenId, newValue ){
  let examenIdInt = validator.toInt(examenId+ "");
  let newValueInt = newValue ? 1 : 0;
  let args = [newValueInt, examenIdInt];

  let sql = 'UPDATE examenes SET predicted = ? WHERE id = ?';

  return new Promise((resolve, reject) => {
    conexionDB.query(sql, args, (er, result, fields) => {
      if (er) {
        reject(er);
        return;
      }
      resolve(result);
    });
  });
}

// Updates a graded entry after manual correction.
// A manual update is always considered verified (verificado = 1).
async function updateCalificadoAutomatizado(calificado){
  let ini = validator.toInt(calificado.ini+ "");
  let fin = validator.toInt(calificado.fin+ "");
  let nota = validator.toFloat(calificado.nota+ "");
  let dni = sanitizeString(calificado.dni);
  let id = validator.toInt(calificado.id+ "");
  let nombre = sanitizeString(calificado.nombre);
  let apellidos = sanitizeString(calificado.apellidos);
  let args = [nombre, apellidos,dni, ini, fin, nota, id];
  let sql = 'UPDATE calificados SET nombre = ?, apellidos = ?,dni = ?,  ini = ?, fin = ?, nota = ?, verificado = 1 WHERE id = ?';

  return new Promise((resolve, reject) => {
    conexionDB.query(sql, args, (er, result, fields) => {
      if (er) console.log(er);
      resolve(result);
    });
  });
}

module.exports = {
  getAlumnosFromAsignatura,
  insertAlumnoCalificado,
  setExamenIsPredicted,
  getCalificadosOrderByIni,
  getAlumnosNoCalificados,
  updateCalificadoAutomatizado
};
