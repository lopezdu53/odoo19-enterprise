def migrate(cr, version):
    """Copia la asignacion antigua board_id (many2one) a la nueva relacion
    many2many tv_calendar_task_board_rel, para no perder los tableros de las
    tareas ya existentes al pasar de 1.0.0 a 1.1.0."""
    # Si no existe la columna antigua no hay nada que migrar.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tv_calendar_task' AND column_name = 'board_id'
    """)
    if not cr.fetchone():
        return

    # Creamos la tabla de relacion con el mismo nombre/columnas que espera
    # el ORM (si aun no existe) y volcamos los datos.
    cr.execute("""
        CREATE TABLE IF NOT EXISTS tv_calendar_task_board_rel (
            task_id integer NOT NULL REFERENCES tv_calendar_task(id) ON DELETE CASCADE,
            board_id integer NOT NULL REFERENCES tv_calendar_board(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, board_id)
        )
    """)
    cr.execute("""
        INSERT INTO tv_calendar_task_board_rel (task_id, board_id)
        SELECT id, board_id FROM tv_calendar_task
        WHERE board_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
