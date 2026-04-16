CREATE DATABASE IF NOT EXISTS `MargotDB`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `MargotDB`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `correo_validacion`;
DROP TABLE IF EXISTS `calificados`;
DROP TABLE IF EXISTS `alumnos`;
DROP TABLE IF EXISTS `examenes`;
DROP TABLE IF EXISTS `asignaturas`;
DROP TABLE IF EXISTS `preferencias`;
DROP TABLE IF EXISTS `usuarios`;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `usuarios` (
  `id` CHAR(24) NOT NULL,
  `correo` CHAR(64) NOT NULL,
  `nombre` VARCHAR(50) NOT NULL,
  `password` CHAR(64) NOT NULL,
  `token` VARCHAR(64) NOT NULL DEFAULT '',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_usuarios_correo` (`correo`),
  UNIQUE KEY `uk_usuarios_nombre` (`nombre`),
  KEY `idx_usuarios_token` (`token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `preferencias` (
  `id` CHAR(24) NOT NULL,
  `cabecera` TINYINT(1) NOT NULL DEFAULT 0,
  `encode` VARCHAR(20) NOT NULL DEFAULT 'utf8',
  `sep` VARCHAR(5) NOT NULL DEFAULT ';',
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_preferencias_usuario`
    FOREIGN KEY (`id`) REFERENCES `usuarios` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `asignaturas` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `acronimo` VARCHAR(20) NOT NULL,
  `color` VARCHAR(20) NOT NULL,
  `curso` VARCHAR(20) NOT NULL,
  `nombre` VARCHAR(120) NOT NULL,
  `usuario` CHAR(24) NOT NULL,
  `visible` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `idx_asignaturas_usuario` (`usuario`),
  KEY `idx_asignaturas_curso` (`curso`),
  CONSTRAINT `fk_asignaturas_usuario`
    FOREIGN KEY (`usuario`) REFERENCES `usuarios` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `alumnos` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `apellidos` VARCHAR(120) NOT NULL,
  `asignatura` INT NOT NULL,
  `dni` VARCHAR(20) NOT NULL,
  `nombre` VARCHAR(120) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_alumnos_asignatura_dni` (`asignatura`, `dni`),
  KEY `idx_alumnos_asignatura` (`asignatura`),
  KEY `idx_alumnos_apellidos` (`apellidos`),
  CONSTRAINT `fk_alumnos_asignatura`
    FOREIGN KEY (`asignatura`) REFERENCES `asignaturas` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `examenes` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `asignatura` INT NOT NULL,
  `fecha` DATE NOT NULL,
  `nombre` VARCHAR(150) NOT NULL,
  `visible` TINYINT(1) NOT NULL DEFAULT 1,
  `disabled` TINYINT(1) NOT NULL DEFAULT 1,
  `saltoPag` INT NOT NULL DEFAULT 0,
  `saltoPagActivo` TINYINT(1) NOT NULL DEFAULT 0,
  `isAvanzado` TINYINT(1) NOT NULL DEFAULT 0,
  `predicted` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_examenes_asignatura` (`asignatura`),
  KEY `idx_examenes_fecha` (`fecha`),
  CONSTRAINT `fk_examenes_asignatura`
    FOREIGN KEY (`asignatura`) REFERENCES `asignaturas` (`id`)
    ON DELETE RESTRICT
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `calificados` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(120) NOT NULL,
  `apellidos` VARCHAR(120) NOT NULL,
  `dni` VARCHAR(20) NOT NULL,
  `examen` INT NOT NULL,
  `ini` INT NOT NULL,
  `fin` INT NOT NULL,
  `nota` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  `verificado` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_calificados_examen` (`examen`),
  KEY `idx_calificados_examen_ini` (`examen`, `ini`),
  KEY `idx_calificados_dni` (`dni`),
  CONSTRAINT `fk_calificados_examen`
    FOREIGN KEY (`examen`) REFERENCES `examenes` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `correo_validacion` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `usuario` CHAR(24) NOT NULL,
  `token` CHAR(32) NOT NULL,
  `creacion` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_correo_validacion_usuario` (`usuario`),
  UNIQUE KEY `uk_correo_validacion_token` (`token`),
  KEY `idx_correo_validacion_usuario_token` (`usuario`, `token`),
  CONSTRAINT `fk_correo_validacion_usuario`
    FOREIGN KEY (`usuario`) REFERENCES `usuarios` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
