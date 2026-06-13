import { Usuario } from "src/models/usuario/usuario";

export const environment = {
  production: true,
  // In Docker, Nginx proxies API and Socket.IO traffic to the backend.
  backend: '',
  session: new Usuario()
};
