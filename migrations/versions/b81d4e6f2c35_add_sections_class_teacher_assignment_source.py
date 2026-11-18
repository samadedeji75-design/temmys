"""add class_level.section, class_arm.class_teacher_id, assignment.source

Revision ID: b81d4e6f2c35
Revises: a3c91d5e7b20
Create Date: 2026-11-18

All changes are additive with safe defaults. Each step skips itself if the
column already exists, so a partially applied or hand-edited database is safe.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b81d4e6f2c35'
down_revision = 'a3c91d5e7b20'
branch_labels = None
depends_on = None


def _columns(table):
    insp = sa.inspect(op.get_bind())
    return {c['name'] for c in insp.get_columns(table)}


def upgrade():
    if 'section' not in _columns('class_level'):
        with op.batch_alter_table('class_level', schema=None) as batch_op:
            batch_op.add_column(sa.Column(
                'section', sa.String(length=20), nullable=False, server_default='secondary'
            ))

    if 'class_teacher_id' not in _columns('class_arm'):
        with op.batch_alter_table('class_arm', schema=None) as batch_op:
            batch_op.add_column(sa.Column('class_teacher_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_class_arm_class_teacher', 'teacher', ['class_teacher_id'], ['id'],
                ondelete='SET NULL',
            )

    if 'source' not in _columns('teacher_subject_assignment'):
        with op.batch_alter_table('teacher_subject_assignment', schema=None) as batch_op:
            batch_op.add_column(sa.Column(
                'source', sa.String(length=20), nullable=False, server_default='manual'
            ))


def downgrade():
    if 'source' in _columns('teacher_subject_assignment'):
        with op.batch_alter_table('teacher_subject_assignment', schema=None) as batch_op:
            batch_op.drop_column('source')

    if 'class_teacher_id' in _columns('class_arm'):
        with op.batch_alter_table('class_arm', schema=None) as batch_op:
            batch_op.drop_constraint('fk_class_arm_class_teacher', type_='foreignkey')
            batch_op.drop_column('class_teacher_id')

    if 'section' in _columns('class_level'):
        with op.batch_alter_table('class_level', schema=None) as batch_op:
            batch_op.drop_column('section')
