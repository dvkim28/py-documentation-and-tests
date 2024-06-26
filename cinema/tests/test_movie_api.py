import os
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from cinema.models import Actor, CinemaHall, Genre, Movie, MovieSession
from cinema.serializers import MovieListSerializer, MovieDetailSerializer
from cinema.tests.test_movies_api import MOVIE_LIST_URL

MOVIE_URL = reverse("cinema:movie-list")
MOVIE_SESSION_URL = reverse("cinema:moviesession-list")


def sample_movie(**params):
    defaults = {
        "title": "Sample movie",
        "description": "Sample description",
        "duration": 90,
    }
    defaults.update(params)

    return Movie.objects.create(**defaults)


def sample_genre(**params):
    defaults = {
        "name": "Drama",
    }
    defaults.update(params)

    return Genre.objects.create(**defaults)


def sample_actor(**params):
    defaults = {"first_name": "George", "last_name": "Clooney"}
    defaults.update(params)

    return Actor.objects.create(**defaults)


def sample_movie_session(**params):
    cinema_hall = CinemaHall.objects.create(name="Blue", rows=20, seats_in_row=20)

    defaults = {
        "show_time": "2022-06-02 14:00:00",
        "movie": None,
        "cinema_hall": cinema_hall,
    }
    defaults.update(params)

    return MovieSession.objects.create(**defaults)


def image_upload_url(movie_id):
    """Return URL for recipe image upload"""
    return reverse("cinema:movie-upload-image", args=[movie_id])


def detail_url(movie_id):
    return reverse("cinema:movie-detail", args=[movie_id])


class MovieImageUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser(
            "admin@myproject.com", "password"
        )
        self.client.force_authenticate(self.user)
        self.movie = sample_movie()
        self.genre = sample_genre()
        self.actor = sample_actor()
        self.movie_session = sample_movie_session(movie=self.movie)

    def tearDown(self):
        self.movie.image.delete()

    def test_upload_image_to_movie(self):
        """Test uploading an image to movie"""
        url = image_upload_url(self.movie.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            res = self.client.post(url, {"image": ntf}, format="multipart")
        self.movie.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("image", res.data)
        self.assertTrue(os.path.exists(self.movie.image.path))

    def test_upload_image_bad_request(self):
        """Test uploading an invalid image"""
        url = image_upload_url(self.movie.id)
        res = self.client.post(url, {"image": "not image"}, format="multipart")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_image_to_movie_list(self):
        url = MOVIE_URL
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            res = self.client.post(
                url,
                {
                    "title": "Title",
                    "description": "Description",
                    "duration": 90,
                    "genres": [1],
                    "actors": [1],
                    "image": ntf,
                },
                format="multipart",
            )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        movie = Movie.objects.get(title="Title")
        self.assertFalse(movie.image)

    def test_image_url_is_shown_on_movie_detail(self):
        url = image_upload_url(self.movie.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            self.client.post(url, {"image": ntf}, format="multipart")
        res = self.client.get(detail_url(self.movie.id))

        self.assertIn("image", res.data)

    def test_image_url_is_shown_on_movie_list(self):
        url = image_upload_url(self.movie.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            self.client.post(url, {"image": ntf}, format="multipart")
        res = self.client.get(MOVIE_URL)

        self.assertIn("image", res.data[0].keys())

    def test_image_url_is_shown_on_movie_session_detail(self):
        url = image_upload_url(self.movie.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as ntf:
            img = Image.new("RGB", (10, 10))
            img.save(ntf, format="JPEG")
            ntf.seek(0)
            self.client.post(url, {"image": ntf}, format="multipart")
        res = self.client.get(MOVIE_SESSION_URL)

        self.assertIn("movie_image", res.data[0].keys())


class UnauthenticatedMovieListAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def detail_movie_url(self, movie_id):
        return reverse("cinema:movie-detail", args=[movie_id])

    def test_unauthenticated_movie_list(self):
        response = self.client.get(MOVIE_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_movie_retrieve(self):
        cinema = sample_movie()
        url = self.detail_movie_url(cinema.pk)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedMovieListAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@test.com",
            password="test_password",
        )
        self.client.force_authenticate(self.user)

    def test_movie_list(self):
        movie = sample_movie()
        actor = sample_actor(first_name="Cruz", last_name="Ramirez")
        genre = sample_genre(name="Action")
        movie.genres.add(genre)
        movie.actors.add(actor)
        response = self.client.get(MOVIE_URL)
        movies = Movie.objects.all()
        serializer = MovieListSerializer(movies, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_filter_movie_by_title(self):
        movie = sample_movie()
        movie1 = sample_movie(
            title="Movie2",
            description="Movie Description",
            duration=110,
        )
        response = self.client.get(MOVIE_URL, {f"title": movie.title})
        serializer_movie = MovieListSerializer(movie)
        serializer_movie1 = MovieListSerializer(movie1)
        self.assertIn(serializer_movie.data, response.data)
        self.assertNotIn(serializer_movie1.data, response.data)

    def test_filter_movie_by_genre(self):
        movie = sample_movie(
            title="Movie",
        )
        movie1 = sample_movie(
            title="Movie1",
        )
        genre = sample_genre(name="Action")
        movie.genres.add(genre)
        serializer_with_genre = MovieListSerializer(movie)
        serializer_without_genre = MovieListSerializer(movie1)
        response = self.client.get(MOVIE_URL, {f"genres": genre.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(serializer_with_genre.data, response.data)
        self.assertNotIn(serializer_without_genre.data, response.data)

    def test_filter_movie_by_actor(self):
        movie = sample_movie()
        movie1 = sample_movie()
        actor = sample_actor(first_name="Igor", last_name="Omlet")
        movie.actors.add(actor)
        serializer_with_actor = MovieListSerializer(movie)
        serializer_without_actor = MovieListSerializer(movie1)
        response = self.client.get(MOVIE_URL, {f"actors": actor.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(serializer_with_actor.data, response.data)
        self.assertNotIn(serializer_without_actor.data, response.data)

    def test_movie_retrieve(self):
        movie = sample_movie()
        movie_url = detail_url(movie.id)
        response = self.client.get(movie_url)
        serializer = MovieDetailSerializer(movie)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_create_movie_forbidden(self):
        response = self.client.post(
            MOVIE_LIST_URL,
            {
                "title": "Test Movie",
                "description": "Test Movie Description",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdmiCinemaTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@test.com",
            password="PASSWORD",
            is_staff=True,
        )
        self.client.force_authenticate(self.user)

    def test_create_movie(self):
        data = {
            "title": "Test Movie",
            "description": "Test Movie Description",
            "duration": 110,
        }
        response = self.client.post(MOVIE_LIST_URL, data)
        movie = Movie.objects.get(id=response.data["id"])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for key in data:
            self.assertEqual(data[key], getattr(movie, key))

    def test_create_movie_with_genre(self):
        genre = sample_genre(name="Action")
        data = {
            "title": "Test Movie",
            "description": "Test Movie Description",
            "duration": 110,
            "genres": [genre.id],
        }
        response = self.client.post(MOVIE_LIST_URL, data)
        movie = Movie.objects.get(id=response.data["id"])
        genres = movie.genres.all()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(genres.count(), 1)
        self.assertIn(genre, genres)
