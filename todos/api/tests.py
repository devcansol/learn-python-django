from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from todos.models import Project, Task


class ProjectApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')
        self.project = Project.objects.create(owner=self.owner, name='Home')

    def test_anonymous_request_is_rejected(self):
        response = self.client.get(reverse('project-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_only_returns_own_projects(self):
        Project.objects.create(owner=self.other, name='Not yours')
        self.client.force_authenticate(self.owner)

        response = self.client.get(reverse('project-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [p['name'] for p in response.data]
        self.assertEqual(names, ['Home'])

    def test_create_assigns_current_user_as_owner(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('project-list'), {'name': 'Work'})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.get(name='Work').owner, self.owner)


class TaskApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='pw12345678')
        self.other = User.objects.create_user('other', password='pw12345678')
        self.project = Project.objects.create(owner=self.owner, name='Home')
        self.other_project = Project.objects.create(owner=self.other, name='Not yours')

    def test_cannot_create_task_under_another_users_project(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('task-list'), {
            'project': self.other_project.pk,
            'title': 'Sneaky task',
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_completed_at_is_read_only_on_the_wire(self):
        self.client.force_authenticate(self.owner)

        response = self.client.post(reverse('task-list'), {
            'project': self.project.pk,
            'title': 'Buy milk',
            'completed_at': '2020-01-01T00:00:00Z',
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(pk=response.data['id'])
        self.assertIsNone(task.completed_at)
