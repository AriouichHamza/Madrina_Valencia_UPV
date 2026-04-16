
CREATE TABLE `alumnos` (
  `id` int NOT NULL AUTO_INCREMENT,
  `apellidos` varchar(256) NOT NULL,
  `asignatura` int NOT NULL,
  `dni` varchar(64) NOT NULL,
  `nombre` varchar(256) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4;

CREATE TABLE `asignaturas` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'id numérico autoincrement',
  `acronimo` varchar(16) NOT NULL COMMENT 'normalmente 3 carácteres, pero se da cierto margen',
  `color` varchar(7) NOT NULL COMMENT 'hexadecimal incluyendo #',
  `curso` varchar(5) NOT NULL COMMENT 'xx/xx',
  `nombre` varchar(256) NOT NULL COMMENT 'nombre de la asignatura',
  `usuario` varchar(24) NOT NULL COMMENT 'id del usuario relacionado con la asignatura',
  `visible` tinyint(1) NOT NULL COMMENT 'campo que se deja por las dudas',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4;

CREATE TABLE `calificados` (
  `id` int NOT NULL AUTO_INCREMENT,
  `apellidos` varchar(256) CHARACTER SET utf8mb4 NOT NULL,
  `dni` varchar(64) NOT NULL,
  `examen` int NOT NULL,
  `fin` int NOT NULL,
  `ini` int NOT NULL,
  `nombre` varchar(256) NOT NULL,
  `nota` float NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4;

CREATE TABLE `examenes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `asignatura` int NOT NULL,
  `fecha` bigint NOT NULL,
  `nombre` varchar(256) NOT NULL,
  `visible` tinyint(1) NOT NULL,
  `disabled` tinyint(1) NOT NULL,
  `saltoPag` int NOT NULL,
  `saltoPagActivo` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4;

CREATE TABLE `preferencias` (
  `id` varchar(24) CHARACTER SET utf8mb4 NOT NULL,
  `cabecera` tinyint(1) NOT NULL,
  `encode` varchar(24) CHARACTER SET utf8mb4 NOT NULL,
  `sep` varchar(1) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `usuarios` (
  `id` varchar(24) CHARACTER SET utf8mb4 NOT NULL COMMENT 'id de 24 carácteres alfabéticos generados aleatoriamente que se usará como código único para identificar al usuario',
  `correo` varchar(256) NOT NULL,
  `nombre` varchar(256) CHARACTER SET utf8mb4 NOT NULL COMMENT 'nombre del usuario',
  `password` varchar(256) CHARACTER SET utf8mb4 NOT NULL COMMENT 'contraseña que no codificaremos aún',
  `token` varchar(64) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `correo_validacion` (
  `usuario` varchar(24) NOT NULL,
  `token` varchar(32) NOT NULL,
  `creacion` timestamp NOT NULL,
  PRIMARY KEY (`usuario`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;