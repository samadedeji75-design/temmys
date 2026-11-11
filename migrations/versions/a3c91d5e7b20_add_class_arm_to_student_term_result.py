"""add class_arm_id to student_term_result

Stores which class a result was finalized in, so promoting a student does
not change the class, subjects or class size shown on their old report
cards. Existing rows are backfilled from each student's current class, so
this must run before any student is promoted.

Revision ID: a3c91d5e7b20
Revises: f47a489a98b7
Create Date: 2026-11-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c91d5e7b20'
down_revision = 'f47a489a98b7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('student_term_result', schema=None) as batch_op:
        batch_op.add_column(sa.Column('class_arm_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_student_term_result_class_arm', 'class_arm', ['class_arm_id'], ['id']
        )

    op.execute(
        "UPDATE student_term_result SET class_arm_id = "
        "(SELECT class_arm_id FROM student WHERE student.id = student_term_result.student_id) "
        "WHERE class_arm_id IS NULL"
    )


def downgrade():
    with op.batch_alter_table('student_term_result', schema=None) as batch_op:
        batch_op.drop_constraint('fk_student_term_result_class_arm', type_='foreignkey')
        batch_op.drop_column('class_arm_id')
