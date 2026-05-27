# Editorial UI

Interfaz local de Streamlit para revisar escenas de screenplay y editar notas
editoriales por escena.

Arranque:

```powershell
uv run streamlit run .\shared\ui\editorial_app.py
```

La app lee:

- `<serie>/processing/screenplay/<session>/escena_XXX.md`
- `<serie>/processing/annotated_screenplay/<session>/escena_XXX.annotated.json`

La app escribe:

- `<serie>/editorial_notes/<session>/escena_XXX.notes.md`

Privacidad:

- Las notas reales en `editorial_notes/` no se versionan.
- Los screenplays y annotated screenplays generados en `processing/` tampoco se
  versionan.
- La app trabaja solo con archivos locales.

Limitaciones actuales:

- No usa LLMs.
- No valida semanticamente las notas.
- Aplica notas para toda la sesion usando la logica de
  `shared/scripts/apply_editorial_notes.py`.
