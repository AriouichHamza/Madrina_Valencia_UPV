
const db = require('../connection');
const archiver = require('archiver');
const fs = require('fs');
const path = require('path');
const pdfPageCounter = require('pdf-page-counter');

const DAL = require('../DAL');

const { exec, execFileSync, spawn } = require("child_process");

const PUBLIC = 'public';
const USER_DATA = 'user_data';
const os = require("os");

const AI_PYTHON_BIN = process.env.AI_PYTHON_BIN ||
  path.resolve(__dirname, '..', '..', '.venv', 'bin', 'python');
const AI_MODULE_PATH = process.env.AI_MODULE_PATH ||
  path.resolve(__dirname, '..', '..', 'AsistenteWebTFGBackendAIModule', 'main.py');
const AI_MODULE_USER_DATA_ROOT = process.env.AI_MODULE_USER_DATA_ROOT ||
  path.resolve(__dirname, '..', USER_DATA);

// Prediction jobs are shared across Socket.IO connections. This prevents the
// upload socket and the exam page socket from starting the same OCR job twice.
const childProcesses = new Map();

function emitPrediction(job, message) {
  job.lastMessage = message;
  for (const subscriber of job.sockets) {
    subscriber.emit('examen-predict-response', message);
  }
}

function resolvePdfName(index, requestedName) {
  const examDir = path.join(AI_MODULE_USER_DATA_ROOT, index);
  if (!fs.existsSync(examDir)) {
    throw new Error(`Exam directory not found: ${examDir}`);
  }

  const requestedBase = path.parse(path.basename(String(requestedName || ''))).name;
  const requestedCandidates = [
    requestedBase,
    requestedBase.replace(/\s+/g, '_'),
  ].filter(Boolean);

  for (const candidate of requestedCandidates) {
    if (fs.existsSync(path.join(examDir, `${candidate}.pdf`))) {
      return candidate;
    }
  }

  const pdfFiles = fs.readdirSync(examDir, { withFileTypes: true })
    .filter(entry => entry.isFile() && path.extname(entry.name).toLowerCase() === '.pdf')
    .map(entry => entry.name);

  if (pdfFiles.length === 1) {
    return path.parse(pdfFiles[0]).name;
  }

  throw new Error(
    `Cannot resolve PDF "${requestedBase}" in ${examDir}; found ${pdfFiles.length} PDF files`
  );
}

async function pdftoppm(read, write, pages, socket, idExam) {

  return new Promise((resolve, reject) => {

    let done = true;
    let ini = 1, fin = 0, cont = 1;
    let contExec = 0, cantExec = 0;
    while (ini <= pages) {

      fin = ((ini + 49) <= pages) ? (ini + 49) : pages;

      let command = pdftoppmCommand(read, ini, fin, write);
      contExec++;
      cantExec++;
      socket.emit('insert-examen-preparar', { idExam: idExam, cont: contExec, total: cantExec * 2 });
      exec(command, (error, stdout, stderr) => {
        if (error) { console.error(error); done = false; }
        contExec++;
        socket.emit('insert-examen-preparar', { idExam: idExam, cont: contExec, total: cantExec * 2 });
        if (contExec == (cantExec * 2)) resolve(done);
      });
      ini = fin + 1;
    }
  });
}

async function pdfunite(readdir, writefile) {

  return new Promise((resolve, reject) => {

    let done = true;
    let listFiles = '';
    let files = fs.readdirSync(readdir);
    files.forEach(file => {
      listFiles += `"${path.join(readdir, file)}" `;
    });
    let command = `pdfunite ${listFiles} "${writefile}"`;
    console.log(command);
    exec(command, (error, stdout, stderr) => {
      if (error) { console.error(error); done = false; }
      resolve(done);
    });
  });

}

async function ps2pdf(readdir, socket, idExam) {

  return new Promise((resolve, reject) => {

    let done = true;
    let contExec = 0, cantExec = 0;
    let files = fs.readdirSync(readdir);
    for (let i = 0; i < files.length; i++) {
      let absolute = path.join(readdir, files[i]);
      let newAbsolute = path.join(readdir, 'ps2pdf-' + files[i]);
      let command = `ps2pdf "${absolute}" "${newAbsolute}"`;
      cantExec++;
      exec(command, (error, stdout, stderr) => {
        if (error) { console.error(error); done = false; }
        contExec++
        socket.emit('insert-examen-generar', { idExam: idExam, cont: contExec, total: cantExec });
        if (contExec == cantExec) resolve(done);
      });

    }
  });
}

async function ps2pdfRemoveFiles(startsWith, readdir) {

  return new Promise((resolve, reject) => {

    let done = true;
    let contExec = 0, cantExec = 0;

    fs.readdir(readdir, (err, files) => {
      if (err) { console.error(err); resolve(false); }

      cantExec = files.length;
      files.forEach(file => {
        contExec++;
        if ((startsWith && file.startsWith('ps2pdf-')) || (!startsWith && !file.startsWith('ps2pdf-'))) {
          let dirfile = path.join(readdir, file);
          fs.unlink(dirfile, (err) => {
            if (err) { console.error(err); done = false; }
            if (contExec == cantExec) resolve(done);
          });
        }
      });
    });
  });

}

function pdftoppmCommand(read, s, f, write) {
  let x = 1240;
  let y = 1750;
  let dpi = 150

  return `pdftoppm -jpeg -f ${s} -l ${f} -r ${dpi} -scale-to-x ${x} -scale-to-y ${y} "${read}" "${write}"`;
}

//Windows & MacOs
//var pdfPoppler = require('pdf-poppler');

const connection = async (socket) => {

  console.log('\x1b[32mclient', socket.id, '\x1b[0m');

  let fileBuffer = [];

  socket.on('insert-alumno', (data) => {
    let args = [data.apellidos.trim(), data.asignatura, data.dni.trim(), data.nombre.trim()];
    let sql = 'INSERT INTO alumnos (apellidos, asignatura, dni, nombre) VALUES (?, ?, ?, ?)';
    db.query(sql, args, (er, result, fields) => {
      data = {
        asignatura: data.asignatura,
        i: data.i
      }
      socket.emit('insert-alumno', data);
    });
  });

  socket.on('insert-examen', (data) => {

    let idUsuario = data.usuario;
    let idAsig = data.asignatura;
    let idExam = data.examen;
    let idPaquete = data.paquete.id
    let op = data.paquete.op;
    let payload = data.paquete.payload;

    let index = idUsuario + '-' + idAsig + '-' + idExam;


    function createImgsWin(dir, fileName) {

      const convertImgSync = async (dir, fileName) => {

        let opts = {
          format: 'jpg',
          out_dir: dir,
          out_prefix: fileName.substring(0, fileName.length - 4),
          page: null
        }

        let readFile = path.join(dir, fileName);
        let pages = await pdfPageCounter(fs.readFileSync(readFile));

        let interval = setInterval(() => {
          let files = fs.readdirSync(dir);
          socket.emit('insert-examen-preparar', { idExam: idExam, cont: files.length, pages: pages.numpages });
        }, 1000);

        await pdfPoppler.convert(readFile, opts);

        clearInterval(interval);
      }

      convertImgSync(dir, fileName).then(() => {
        let sql = 'UPDATE examenes SET disabled = ? WHERE id = ?';
        db.query(sql, [0, idExam], (er, result, fields) => {
          socket.emit('insert-examen-listo', idExam);
        });
      });

    }

    async function insertExamenError(message) {
      console.error(message);

      let dir = path.join(__dirname, '..', USER_DATA, index);
      fs.rm(dir, { recursive: true }, (err) => {
        if (err) { console.error('No se ha podido borrar la carpeta ' + index); }
      });

      db.query('DELETE FROM examenes WHERE id = ?', [idExam], (er, result, fields) => {
        if (er) { console.error('No se ha podido borrar de la base de datos el examen ' + index); }
        socket.emit('insert-examen-error', { idExam: idExam, message: 'Error al procesar el examen' });
      });
    }

    async function mergeFiles(baseName, baseIndex, cant) {

      for (let i = 0; i < cant; i++) {
        if (fileBuffer[baseIndex + i] == undefined || !fileBuffer[baseIndex + i].ready) return;
      }

      for (let i = 0; i < cant; i++) { delete fileBuffer[baseIndex + i]; }

      let readdir = path.join(__dirname, '..', USER_DATA, index);
      let writefile = path.join(readdir, baseName);

      //esto puede que se pueda eliminar
      let done = await ps2pdf(readdir, socket, idExam);
      if (!done) { insertExamenError('ps2pdf'); return; }

      done = await ps2pdfRemoveFiles(false, readdir);
      if (!done) { insertExamenError('false ps2pdfRemoveFiles'); return; }

      done = await pdfunite(readdir, writefile);
      if (!done) { insertExamenError('pdfunite'); return; }

      socket.emit('insert-examen-generar', { idExam: idExam, cont: 1, total: 1 });

      done = await ps2pdfRemoveFiles(true, readdir);
      if (!done) { insertExamenError('true ps2pdfRemoveFiles'); return; }

      if (process.platform == 'linux') {

        let readFile = path.join(readdir, baseName);
        let writeFile = path.join(readdir, path.parse(readFile).name);

        let pages = null;
        try {
          pages = (await pdfPageCounter(fs.readFileSync(readFile))).numpages;
        } catch (e) {
          insertExamenError('pdfPageCounter'); return;
        }
        if (pages == 0) { insertExamenError('pdfPageCounter'); return; }

        socket.emit('insert-examen-preparar', { idExam: idExam, cont: 0, total: 1 });

        done = await pdftoppm(readFile, writeFile, pages, socket, idExam);
        if (!done) { insertExamenError('pdftoppm'); return; }

        let sql = 'UPDATE examenes SET disabled = ? WHERE id = ?';
        let args = [0, idExam];
        db.query(sql, args, (er, result, fields) => {
          if (er) {
            console.error('Error al actualizar el examen ' + index);
            socket.emit('insert-examen-error', { idExam: idExam, message: 'Error al procesar el examen' });
          } else {
            socket.emit('insert-examen-listo', { idExam: idExam });
            db.syncQuery('SELECT isAvanzado FROM examenes WHERE id = ?', [idExam])
              .then(rows => {
                if (rows && rows.length === 1 && Number(rows[0].isAvanzado) === 1) {
                  spawnPrediction(index, path.parse(baseName).name, socket);
                }
              })
              .catch(err => {
                console.error(`Cannot check automatic prediction for exam ${idExam}:`, err);
              });
          }
        });

      } else {
        createImgsWin(readdir, baseName);
      }
    }

    switch (op) {
      case 'new-file':
        fileBuffer[idPaquete] = { nombre: payload, data: '', ready: false };
        socket.emit('insert-examen-procesar', idExam);
        break;
      case 'fin-file':

        let baseName = payload.split(':')[0];
        let baseIndex = payload.split(':')[1];
        let cant = parseInt(payload.split(':')[2]);

        socket.emit('insert-examen-procesar', idExam);

        let fileName = fileBuffer[idPaquete].nombre;
        let data = fileBuffer[idPaquete].data;
        data = data.split(';base64,').pop();

        let dir = path.join(__dirname, '..', USER_DATA, index, fileName.replace(' ', '_'));
        let done = true;
        fs.writeFileSync(dir, data, 'base64', (error) => {
          if (error) {
            console.error(error);
            done = false;
          }
        });

        if (!done) { insertExamenError('writeFileSync base64'); return; }

        socket.emit('insert-examen-crear', idExam);
        fileBuffer[idPaquete].ready = true;

        mergeFiles(baseName.replace(' ', '_'), baseIndex, cant);

        break;
      default:
        fileBuffer[idPaquete].data += payload;
        socket.emit('insert-examen-procesar', idExam);
        break;
    }
  });
  //Devuelve las imagenes de un examen dados los id de usuario, asignatura y examen
  socket.on('select-examen-imgs', (data) => {

    let idUsuario = data.usuario;
    let idAsig = data.asignatura;
    let idExam = data.examen;
    let index = idUsuario + '-' + idAsig + '-' + idExam;

    function splitString(base64) {

      const length = 1024 * 256;
      let split = [];

      while (base64.length > length) {
        let o = base64.substring(0, length);
        let f = base64.substring(length, base64.length);
        split.push(o);
        base64 = f;
      }
      split.push(base64.substring(0, base64.length));

      return split;
    }

    let readdir = path.join(__dirname, '..', USER_DATA, index);
    let files = [];
    if (fs.existsSync(readdir)) {
      files = fs.readdirSync(readdir);
    }

    files.forEach(file => {

      if (path.extname(file).toLowerCase() == '.jpg') {
        let data = fs.readFileSync(path.join(readdir, file), { encoding: 'base64' });
        let split = splitString(data);
        socket.emit('select-examen-imgs', 'new-img');
        socket.emit('select-examen-imgs', 'data:image/jpg;base64,');
        split.forEach(paquete => {
          socket.emit('select-examen-imgs', paquete);
        });
        socket.emit('select-examen-imgs', 'fin-imgs');
      };
    });
    //Evento que indica que se han enviado todas las imagenes
    socket.emit('select-examen-imgs', 'fin-all');

  });

  socket.on('select-examen-zip', async (data) => {

    let examen = { nombre: '', fecha: 0 };

    let idUsuario = data.usuario;
    let idAsig = data.asignatura;
    let idExam = data.examen;
    let index = idUsuario + '-' + idAsig + '-' + idExam;

    examen = (await db.syncQuery('SELECT * FROM examenes WHERE id = ?', [idExam]))[0];

    let dirPrivate = path.join(__dirname, '..', USER_DATA, index);
    let dirPublic = path.join(__dirname, '..', PUBLIC, index);

    let dirExamen = path.join(dirPublic, examen.nombre)
    let dirCSV = path.join(dirExamen, 'csv');
    let dirExamenes = path.join(dirExamen, 'examenes');

    if (fs.existsSync(dirPublic)) { fs.rmSync(dirPublic, { recursive: true }); }
    fs.mkdirSync(dirPublic);
    fs.mkdirSync(dirExamen);
    fs.mkdirSync(dirCSV);
    fs.mkdirSync(dirExamenes);

    let progressTotal = 0;
    let progress = 0;

    function dniWithoutCheckLetter(value) {
      const dni = String(value || '').trim().toUpperCase();

      if (/^\d+[A-Z]$/.test(dni) || /^[XYZNP]\d+[A-Z]$/.test(dni)) {
        return dni.slice(0, -1);
      }

      return dni;
    }

    function writeZIP() {

      if (progress < progressTotal) {
        let paquete = {
          done: false,
          progress: progress,
          total: progressTotal,
          perc: Math.round(progress / progressTotal)
        }
        console.log('progress: %d progressTotal', progress, progressTotal);
        socket.emit('select-examen-zip', paquete);
        return;
      }

      let date = new Date(examen.fecha);
      let year = date.getFullYear();
      let month = ((date.getMonth() + 1) < 9) ? '0' + date.getMonth() + 1 : date.getMonth() + 1;
      let day = (date.getDate() < 9) ? '0' + date.getDate() : date.getDate();
      let filename = `${year}${month}${day}-${examen.nombre.replace(' ', '_')}.zip`;
      let filePath = path.join(dirPublic, filename);

      const output = fs.createWriteStream(filePath);
      const archive = archiver('zip', { zlib: { level: 9 } });

      output.on('close', function () {
        fs.rmSync(dirCSV, { recursive: true });
        fs.rmSync(dirExamenes, { recursive: true });

        let paquete = {
          done: true,
          progress: progressTotal,
          total: progressTotal,
          filename: filename,
          url: PUBLIC + '/' + index + '/' + filename
        }
        console.log('emit on close');
        socket.emit('select-examen-zip', paquete);
      });
      console.log('archive');
      archive.pipe(output);
      archive.directory(dirExamen, examen.nombre);
      archive.finalize();
    }

    function writeCSV(calificados) {

      let csvInfo = 'ID estudiante;Apellidos;Nombre;Nota;Inicio;Fin\n';
      let csvPadrino = 'ID estudiente;Nota\n';

      calificados.forEach(c => {
        const exportedDni = dniWithoutCheckLetter(c.dni);
        csvInfo += `${exportedDni};${c.apellidos};${c.nombre};${c.nota};${c.ini};${c.fin}\n`;
        if (exportedDni.length > 0) { csvPadrino += `${exportedDni};${c.nota}\n`; }
      });
      csvInfo = csvInfo.trim();
      csvPadrino = csvPadrino.trim();

      let filenameInfo = 'detalles.csv';
      let filenameExamenes = examen.nombre.replace(' ', '_') + '_notas_padrino.csv';

      fs.writeFileSync(path.join(dirCSV, filenameInfo), csvInfo);
      fs.writeFileSync(path.join(dirCSV, filenameExamenes), csvPadrino);

      progress++;
      writeZIP();
    }
  function writePDF(calificados) {
    let sinNombre = 0;

    const userHomeDir = os.homedir();
    const scanBat = path.join(userHomeDir, 'exam_scan', 'sube.bat');
    const destBat = path.join(dirExamenes, 'sube.bat');

    console.log('scanBat: %s destBat: %s', scanBat, destBat);

    // Copier sube.bat seulement s'il existe
    if (fs.existsSync(scanBat)) {
      fs.copyFileSync(scanBat, destBat);
    } else {
      console.log('sube.bat absent, copie ignorée');
    }

    calificados.forEach(c => {
      let filename = '';
      const exportedDni = dniWithoutCheckLetter(c.dni);

      if (exportedDni.length > 0) {
        let alumnoDNI = exportedDni;
        let examenNombre = examen.nombre.replace(/ /g, '_');
        let alumnoNombre = (
          c.nombre.replace(/ /g, '_') +
          '_' +
          c.apellidos.replace(/ /g, '_')
        )
          .toLowerCase()
          .normalize("NFD")
          .replace(/\p{Diacritic}/gu, "");

        filename = `${alumnoDNI}_${examenNombre}_${alumnoNombre}.pdf`;
      } else {
        filename = 'XXXXXXXXX_Sin_nombre_' + (++sinNombre) + '.pdf';
      }

      const writePath = path.join(dirExamenes, filename);
      const readPath = path.join(dirPrivate, examen.nombre.replace(/ /g, '_') + '.pdf');
      const firstPage = Number(c.ini);
      const lastPage = Number(c.fin);
      const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'madrina-pages-'));
      const pagePattern = path.join(temporaryDirectory, 'page-%d.pdf');

      try {
        if (!Number.isInteger(firstPage) || !Number.isInteger(lastPage) ||
            firstPage < 1 || lastPage < firstPage) {
          throw new Error(`Invalid page range: ${c.ini}-${c.fin}`);
        }

        execFileSync('pdfseparate', [
          '-f', String(firstPage),
          '-l', String(lastPage),
          readPath,
          pagePattern,
        ], { stdio: 'ignore' });

        const pageFiles = fs.readdirSync(temporaryDirectory)
          .filter(file => /^page-\d+\.pdf$/.test(file))
          .sort((a, b) => {
            const pageA = Number(a.match(/\d+/)[0]);
            const pageB = Number(b.match(/\d+/)[0]);
            return pageA - pageB;
          })
          .map(file => path.join(temporaryDirectory, file));

        if (pageFiles.length === 0) {
          throw new Error(`No page extracted for range ${firstPage}-${lastPage}`);
        }

        execFileSync('pdfunite', [...pageFiles, writePath], { stdio: 'ignore' });
      } catch (err) {
        console.error('Erreur writePDF/poppler:', err.message);
      } finally {
        fs.rmSync(temporaryDirectory, { recursive: true, force: true });
        progress++;
        writeZIP();
      }
    });
  }

      let sql = 'SELECT * FROM calificados WHERE examen = ?';
      db.query(sql, [idExam], (er, result, fields) => {
        progressTotal = result.length + 1;
        writeCSV(result);
        writePDF(result);
      });
    });

  async function spawnPrediction(index, requestedPdfName, socket) {
    const runningJob = childProcesses.get(index);
    if (runningJob) {
      runningJob.sockets.add(socket);
      if (runningJob.lastMessage) {
        socket.emit('examen-predict-response', runningJob.lastMessage);
      }
      return;
    }

    const parts = index.split('-');
    if (parts.length !== 3) {
      socket.emit('examen-predict-response', `error Invalid exam index: ${index}`);
      return;
    }

    const asignatura = parts[1];
    const examen = parts[2];

    const job = {
      child: null,
      completed: false,
      failed: false,
      finalizing: null,
      lastMessage: 'progress 0 Preparando el modelo IA',
      sockets: new Set([socket]),
      stderr: '',
    };
    childProcesses.set(index, job);
    emitPrediction(job, job.lastMessage);

    let progressconversion = 0;
    let progressFindStructure = 0;

    const failPrediction = (message) => {
      if (job.failed || job.completed) return;
      job.failed = true;
      console.error(`AI prediction failed for ${index}: ${message}`);
      emitPrediction(job, `error ${message}`);
    };

    const processLine = (rawLine) => {
      const element = rawLine.trim();
      if (!element) return;

      const firstSpace = element.indexOf(' ');
      const preamble = firstSpace === -1 ? element : element.slice(0, firstSpace);
      const lineData = firstSpace === -1 ? '' : element.slice(firstSpace + 1).trim();

      switch (preamble) {
        case 'progress': {
          const progressParts = lineData.split(' ');
          const progress = Number(progressParts[0]);
          const state = progressParts.slice(1).join(' ').trim();

          if (state === 'Buscando DNIs en páginas' && progress > progressFindStructure) {
            progressFindStructure = progress;
            emitPrediction(job, element);
          } else if (state === 'Convirtiendo PDF a imagenes' && progress > progressconversion) {
            progressconversion = progress;
            emitPrediction(job, element);
          } else if (state === 'Preparando el modelo IA') {
            emitPrediction(job, element);
          }
          break;
        }
        case 'new-calificado':
          try {
            job.predictions.push(JSON.parse(lineData));
          } catch (err) {
            failPrediction(`Invalid AI result: ${err.message}`);
          }
          break;
        case 'done':
          if (!job.finalizing && !job.failed) {
            job.finalizing = (async () => {
              await Promise.all(
                job.predictions.map(alumno => DAL.insertAlumnoCalificado(alumno, false))
              );
              await DAL.setExamenIsPredicted(examen, true);
              job.completed = true;
              emitPrediction(job, element);
            })().catch(err => failPrediction(`Cannot save AI results: ${err.message}`));
          }
          break;
        case 'error':
          failPrediction(lineData || 'Unknown AI error');
          break;
        default:
          console.log(`[AI ${index}] ${element}`);
      }
    };

    try {
      fs.accessSync(AI_PYTHON_BIN, fs.constants.X_OK);
      fs.accessSync(AI_MODULE_PATH, fs.constants.R_OK);

      const pdfNameNoExt = resolvePdfName(index, requestedPdfName);
      const students = await DAL.getAlumnosFromAsignatura(asignatura);
      job.predictions = [];

      const args = [AI_MODULE_PATH, index, pdfNameNoExt, JSON.stringify(students)];
      const child = spawn(AI_PYTHON_BIN, args, {
        cwd: path.dirname(AI_MODULE_PATH),
        env: {
          ...process.env,
          AI_MODULE_USER_DATA_ROOT,
          PYTHONUNBUFFERED: '1',
        },
      });
      job.child = child;

      let stdoutBuffer = '';
      child.stdout.on('data', (data) => {
        stdoutBuffer += data.toString('utf-8');
        const lines = stdoutBuffer.split(/\r?\n/);
        stdoutBuffer = lines.pop();
        lines.forEach(processLine);
      });

      child.stderr.on('data', (data) => {
        const message = data.toString('utf-8');
        job.stderr = (job.stderr + message).slice(-8000);
        console.error(`[AI ${index}] ${message.trimEnd()}`);
      });

      child.on('error', (err) => {
        failPrediction(`Cannot start Python process: ${err.message}`);
      });

      child.on('close', async (code, signal) => {
        if (stdoutBuffer.trim()) processLine(stdoutBuffer);
        if (job.finalizing) await job.finalizing;

        if (!job.completed && !job.failed) {
          const detail = job.stderr.trim().split(/\r?\n/).pop();
          failPrediction(
            `AI process stopped before completion (code=${code}, signal=${signal || 'none'})` +
            (detail ? `: ${detail}` : '')
          );
        }
        childProcesses.delete(index);
      });
    } catch (err) {
      failPrediction(err.message);
      childProcesses.delete(index);
    }
  }

  socket.on('examen-predict', async (data) => {
    let usuario = data.usuario;
    let asignatura = data.asignatura;
    let examen = data.examen;
    let asignaturaNom = data.asignaturaNom;
    let index = usuario + '-' + asignatura + '-' + examen;

    spawnPrediction(index, asignaturaNom, socket);
  });

  socket.on('examen-predict-kill', (data) => {
    const index = `${data.usuario}-${data.asignatura}-${data.examen}`;
    const job = childProcesses.get(index);
    if (job && job.child) {
      job.failed = true;
      job.child.kill('SIGTERM');
      emitPrediction(job, 'error Predicción cancelada');
    }
  });

}


const use = (server) => {

  let pingTimeout = 5 * 60 * 1000;

  console.log('socket - pingTimeout:', pingTimeout);

  var io = require('socket.io')(server, { pingTimeout: pingTimeout });

  io.on('connection', connection);
}

module.exports = use;
