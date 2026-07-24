from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Project, Task


class ProjectTaskModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.project = Project.objects.create(owner=self.owner, name='Home')

    def test_str_methods(self):
        task = Task.objects.create(project=self.project, title='Buy milk')
        self.assertEqual(str(self.project), 'Home')
        self.assertEqual(str(task), 'Buy milk')

    def test_completed_at_is_stamped_when_marked_done(self):
        task = Task.objects.create(project=self.project, title='Buy milk')
        self.assertIsNone(task.completed_at)

        task.is_done = True
        task.save()
        task.refresh_from_db()
        self.assertIsNotNone(task.completed_at)

    def test_completed_at_clears_when_marked_not_done(self):
        task = Task.objects.create(project=self.project, title='Buy milk', is_done=True)
        self.assertIsNotNone(task.completed_at)

        task.is_done = False
        task.save()
        task.refresh_from_db()
        self.assertIsNone(task.completed_at)


class ProjectViewOwnershipTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')
        self.project = Project.objects.create(owner=self.owner, name='Home')
        self.task = Task.objects.create(project=self.project, title='Buy milk')

    def test_owner_can_view_project_detail(self):
        self.client.login(username='owner', password='pw12345678')
        response = self.client.get(reverse('todos:project-detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 200)

    def test_other_user_gets_404_on_project_detail(self):
        self.client.login(username='other', password='pw12345678')
        response = self.client.get(reverse('todos:project-detail', kwargs={'pk': self.project.pk}))
        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_edit_task(self):
        self.client.login(username='other', password='pw12345678')
        response = self.client.post(
            reverse('todos:task-update', kwargs={'pk': self.task.pk}),
            {'title': 'Hijacked', 'is_done': False},
        )
        self.assertEqual(response.status_code, 404)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Buy milk')

    def test_project_create_assigns_current_user_as_owner(self):
        self.client.login(username='owner', password='pw12345678')
        response = self.client.post(reverse('todos:project-create'), {'name': 'Work', 'description': ''})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(name='Work', owner=self.owner).exists())
