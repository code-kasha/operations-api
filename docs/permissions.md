# Staff permissions

Business roles belong to employee records: `admin`, `hr`, `manager`, and
`employee` (default). An active Django superuser can bootstrap the first
operations admin. `is_staff` alone grants no business access. Accounts without
an active employee record cannot access staff data.

| Operation | Admin / superuser | HR | Manager | Employee |
| --- | --- | --- | --- | --- |
| Read employees | All | All | Own department | Self |
| Read departments | All | All | Own department | Own department |
| Create/update employees | Yes | Yes | No | No |
| Create/update/delete empty departments | Yes | Yes | No | No |
| Assign business roles | Yes | No | No | No |
| Read staff activity | All | All | No | No |
| Read shifts/holidays | All | All | All | All |
| Manage shifts/assignments/holidays | Yes | Yes | No | No |
| Read assignments/attendance/leave | All | All | Own department | Self |
| Clock in/out, request leave | Self with employee record | Self | Self | Self |
| Review leave (never self) | Other employees | Others except admins | Ordinary employees in own department | No |
| Read office timesheets/overtime | All | All | Own department | Self |
| Create/submit/cancel office work | Self with employee record | Self | Self | Self |
| Review office work (never self) | Other employees | Others except admins | Ordinary employees in own department | No |
| Read salary structures | All | All | Self | Self |
| Create/delete salary structures (never self) | Others | Others except admins | No | No |
| Manage pay runs | Yes | Yes | No | No |
| Read payslips | All | All | Self, locked runs | Self, locked runs |

Payroll visibility does not follow department scope: managers see only their own pay. See [payroll rules](payroll.md).

Office operations require the office sector. Entries can be changed only by the
owner while the timesheet is a draft. Approved work is immutable. See
[office rules](offices.md) for the supported transitions.

HR cannot edit an operations admin or their own department/active status.
Operations admins cannot deactivate or change their own role through the API.
These restrictions prevent accidental loss of administrative access and HR
changes to privileged accounts. Use another admin or the trusted superuser.

Employee accounts must already exist (create them through Django admin).
Linking Django staff/superuser accounts is forbidden; administrative accounts
stay separate from employee identities. Employee-account links are immutable.
Employee deactivation removes business access immediately, including with an
already-issued JWT, but does not disable login or the account's `/auth/me/`.

Hidden detail records return 404, including for write attempts. Writes against
visible records without permission return 403. List endpoints show only visible
records (including an empty activity list for non-HR/admin users). Employee
deletion is disabled; deactivate records to preserve history.
Departments referenced by employees cannot be deleted.

The Django admin exposes staff records and activity as read-only for superusers;
use the API to mutate business data so validation and auditing stay consistent.
