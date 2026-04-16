var createError = require('http-errors');
var express = require('express');
var fs = require('fs');
var path = require('path');
var cookieParser = require('cookie-parser');
var logger = require('morgan');
var cors = require('cors');

var db = require('./connection');

var interceptorRouter = require('./routes/interceptor');
var apiRouter = require('./routes/api');
var loginRouter = require('./routes/login');

var app = express();


if (!fs.existsSync(path.join(__dirname, 'public'))) {
  fs.mkdirSync( path.join(__dirname, 'public') );
}

if (!fs.existsSync(path.join(__dirname, 'user_data'))) {
  fs.mkdirSync( path.join(__dirname, 'user_data') );
}

db.isConnected((connected) => {
  if (!connected) {
    console.log('No se ha podido conectar con la base de datos');
    process.exit(0);
  }
});

// view engine setup and keep connection for each route
app.set('views', path.join(__dirname, 'views'));
app.set('view engine', 'pug');

app.use(logger('dev'));
app.use(express.json());
app.use(express.urlencoded({ extended: false }));
app.use(cookieParser());
app.use('/info', express.static(path.join(__dirname, 'info')));
app.use('/public', express.static(path.join(__dirname, 'public')));
app.use(cors({ origin: '*' }));

app.use('/api', interceptorRouter);
app.use('/api', apiRouter);
app.use('/login', loginRouter);

// catch 404 and forward to error handler
app.use(function(req, res, next) {
  next(createError(404));
});


// error handler
app.use(function(err, req, res, next) {
  // set locals, only providing error in development
  res.locals.message = err.message;
  res.locals.error = req.app.get('env') === 'development' ? err : {};

  // render the error page
  res.status(err.status || 500);
  res.render('error');
});


module.exports = app;
