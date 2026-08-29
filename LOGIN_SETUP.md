# Home Art Furniture – Staff Account Management

The Home Art Furniture platform operates with a single shared staff account without public registration or email-based password reset for security.

Staff accounts are managed directly through Django's administrative CLI commands on the server.

---

## 1. Initial Setup: Create the Staff Account

Run the following command in the project environment to create the administrative staff user:

```bash
# On Linux/macOS/EC2:
python manage.py createsuperuser

# On Windows:
python manage.py createsuperuser
```

You will be prompted to enter:
1. **Username**: (e.g. `admin` or `staff`)
2. **Email**: (optional, can be left blank or `admin@homeartfurniture.store`)
3. **Password**: Choose a strong password
4. **Password (again)**: Confirm password

Once created, log in at:
`http://<your-domain-or-ip>/accounts/login/` (or directly at `/`)

---

## 2. Reset or Change Password

If the store owner forgets the password or needs to update it:

```bash
python manage.py changepassword <username>
```

Example:
```bash
python manage.py changepassword admin
```

You will be prompted to enter and confirm the new password without needing the old password.

---

## 3. Verify Existing Accounts

To view all existing user accounts in the system:

```bash
python manage.py shell -c "from django.contrib.auth.models import User; print(list(User.objects.values_list('username', flat=True)))"
```
