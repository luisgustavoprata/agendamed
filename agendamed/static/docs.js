// Inicializa o Swagger UI com a especificação gerada pela própria API.
window.ui = SwaggerUIBundle({
  url: "/openapi.json",
  dom_id: "#swagger-ui",
  persistAuthorization: true,
  validatorUrl: null,
  docExpansion: "list",
});
