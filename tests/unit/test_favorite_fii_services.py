import pytest
from unittest.mock import patch, MagicMock
from services.favorite_fii_services import (
    list_favorites_fii, view_favorite_fii, new_favorite_fii, edit_favorite_fii, delete_favorite_fii,
    add_favorite_fii, remove_favorite_fii
)
from models.favorite_fiis import FavoriteFii
from models.fii import Fii
from models.user import User


class TestFavoriteFiiServices:
    
    def test_list_favorites_fii_success(self, app, sample_favorite_fii, sample_user):
        """Test successful listing of favorite FIIs"""
        with app.app_context():
            mock_favorite = MagicMock(spec=FavoriteFii)
            mock_favorite.to_json.return_value = {
                'id': 1,
                'user_id': 1,
                'fii_ticker': 'KNRI11',
                'ceiling_price': 110.0,
                'target_price': 100.0
            }
            
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.filter_by.return_value.all.return_value = [mock_favorite]
                
                result, status_code = list_favorites_fii(sample_user.id)
                
                assert status_code == 200
                result_data = result.get_json()
                assert len(result_data) == 1
                assert result_data[0]['fii_ticker'] == 'KNRI11'

    def test_list_favorites_fii_empty(self, app):
        """Test listing favorite FIIs when no favorites exist"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.filter_by.return_value.all.return_value = []
                
                result, status_code = list_favorites_fii(1)
                
                assert status_code == 200
                result_data = result.get_json()
                assert result_data == []

    def test_list_favorites_fii_with_exception(self, app):
        """Test listing favorite FIIs when an exception occurs"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.filter_by.side_effect = Exception("Database error")
                
                result, status_code = list_favorites_fii(1)
                
                assert status_code == 500
                result_data = result.get_json()
                assert "Error in list_favorites_fii" in result_data['message']

    def test_view_favorite_fii_success(self, app, sample_favorite_fii):
        """Test viewing a specific favorite FII"""
        with app.app_context():
            mock_favorite = MagicMock(spec=FavoriteFii)
            mock_favorite.to_json.return_value = {
                'id': 1,
                'user_id': 1,
                'fii_ticker': 'KNRI11',
                'ceiling_price': 110.0,
                'target_price': 100.0
            }
            
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.get.return_value = mock_favorite
                
                result, status_code = view_favorite_fii(1)
                
                assert status_code == 200
                result_data = result.get_json()
                assert result_data['fii_ticker'] == 'KNRI11'

    def test_view_favorite_fii_not_found(self, app):
        """Test viewing a favorite FII that doesn't exist"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.get.return_value = None
                
                result, status_code = view_favorite_fii(999)
                
                assert status_code == 404
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite not found'

    def test_view_favorite_fii_with_exception(self, app):
        """Test viewing a favorite FII when an exception occurs"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.get.side_effect = Exception("Database error")
                
                result, status_code = view_favorite_fii(1)
                
                assert status_code == 500
                result_data = result.get_json()
                assert "Error in view_favorite_fii" in result_data['message']

    def test_new_favorite_fii_success(self, app):
        """Test creating a new favorite FII"""
        with app.app_context():
            favorite_data = {
                'user_id': 1,
                'fii_ticker': 'KNRI11',
                'ceiling_price': 110.0,
                'target_price': 100.0
            }
            
            with patch('services.favorite_fii_services.User.query') as mock_user_query, \
                 patch('services.favorite_fii_services.Fii.query') as mock_fii_query, \
                 patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_user_query.get.return_value = MagicMock()
                mock_fii_query.get.return_value = MagicMock()
                mock_favorite_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                
                result, status_code = new_favorite_fii(favorite_data)
                
                assert status_code == 201
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite added successfully'

    def test_new_favorite_fii_user_not_found(self, app):
        """Test creating a favorite FII with non-existent user"""
        with app.app_context():
            favorite_data = {
                'user_id': 999,
                'fii_ticker': 'KNRI11',
                'ceiling_price': 110.0,
                'target_price': 100.0
            }
            
            with patch('services.favorite_fii_services.User.query') as mock_user_query:
                mock_user_query.get.return_value = None
                
                result, status_code = new_favorite_fii(favorite_data)
                
                assert status_code == 404
                result_data = result.get_json()
                assert result_data['message'] == 'User not found'

    def test_new_favorite_fii_fii_not_found(self, app):
        """Test creating a favorite FII with non-existent FII"""
        with app.app_context():
            favorite_data = {
                'user_id': 1,
                'fii_ticker': 'INVALID',
                'ceiling_price': 110.0,
                'target_price': 100.0
            }
            
            with patch('services.favorite_fii_services.User.query') as mock_user_query, \
                 patch('services.favorite_fii_services.Fii.query') as mock_fii_query:
                
                mock_user_query.get.return_value = MagicMock()
                mock_fii_query.get.return_value = None
                
                result, status_code = new_favorite_fii(favorite_data)
                
                assert status_code == 404
                result_data = result.get_json()
                assert result_data['message'] == 'FII not found'

    def test_new_favorite_fii_already_exists(self, app):
        """Test creating a favorite FII that already exists"""
        with app.app_context():
            favorite_data = {
                'user_id': 1,
                'fii_ticker': 'KNRI11',
                'ceiling_price': 110.0,
                'target_price': 100.0
            }
            
            with patch('services.favorite_fii_services.User.query') as mock_user_query, \
                 patch('services.favorite_fii_services.Fii.query') as mock_fii_query, \
                 patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                
                mock_user_query.get.return_value = MagicMock()
                mock_fii_query.get.return_value = MagicMock()
                mock_favorite_query.filter_by.return_value.first.return_value = MagicMock()
                
                result, status_code = new_favorite_fii(favorite_data)
                
                assert status_code == 400
                result_data = result.get_json()
                assert result_data['message'] == 'This FII is already favorited by this user'

    def test_new_favorite_fii_with_exception(self, app):
        """Test creating a favorite FII when an exception occurs"""
        with app.app_context():
            favorite_data = {
                'user_id': 1,
                'fii_ticker': 'KNRI11',
                'ceiling_price': 110.0,
                'target_price': 100.0
            }
            
            with patch('services.favorite_fii_services.User.query') as mock_user_query, \
                 patch('services.favorite_fii_services.Fii.query') as mock_fii_query, \
                 patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_user_query.get.return_value = MagicMock()
                mock_fii_query.get.return_value = MagicMock()
                mock_favorite_query.filter_by.return_value.first.return_value = None
                mock_db_session.add.side_effect = Exception("Database error")
                
                result, status_code = new_favorite_fii(favorite_data)
                
                assert status_code == 500
                result_data = result.get_json()
                assert "Error in new_favorite_fii" in result_data['message']

    def test_edit_favorite_fii_success(self, app):
        """Test editing an existing favorite FII"""
        with app.app_context():
            favorite_data = {
                'ceiling_price': 115.0,
                'target_price': 105.0
            }
            
            mock_favorite = MagicMock(spec=FavoriteFii)
            
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_favorite_query.get.return_value = mock_favorite
                mock_db_session.commit = MagicMock()
                
                result, status_code = edit_favorite_fii(1, favorite_data)
                
                assert status_code == 200
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite edited successfully'
                
                # Verify that the attributes were set
                for key, value in favorite_data.items():
                    assert getattr(mock_favorite, key) == value

    def test_edit_favorite_fii_not_found(self, app):
        """Test editing a favorite FII that doesn't exist"""
        with app.app_context():
            favorite_data = {'ceiling_price': 115.0}
            
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.get.return_value = None
                
                result, status_code = edit_favorite_fii(999, favorite_data)
                
                assert status_code == 404
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite not found'

    def test_edit_favorite_fii_with_exception(self, app):
        """Test editing a favorite FII when an exception occurs"""
        with app.app_context():
            favorite_data = {'ceiling_price': 115.0}
            
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_favorite_query.get.return_value = MagicMock()
                mock_db_session.commit.side_effect = Exception("Database error")
                
                result, status_code = edit_favorite_fii(1, favorite_data)
                
                assert status_code == 500
                result_data = result.get_json()
                assert "Error in edit_favorite_fii" in result_data['message']

    def test_delete_favorite_fii_success(self, app):
        """Test deleting an existing favorite FII"""
        with app.app_context():
            mock_favorite = MagicMock(spec=FavoriteFii)
            
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_favorite_query.get.return_value = mock_favorite
                mock_db_session.delete = MagicMock()
                
                result, status_code = delete_favorite_fii(1)
                
                assert status_code == 200
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite deleted successfully'

    def test_delete_favorite_fii_not_found(self, app):
        """Test deleting a favorite FII that doesn't exist"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.get.return_value = None
                
                result, status_code = delete_favorite_fii(999)
                
                assert status_code == 404
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite not found'

    def test_delete_favorite_fii_with_exception(self, app):
        """Test deleting a favorite FII when an exception occurs"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_favorite_query.get.return_value = MagicMock()
                mock_db_session.delete.side_effect = Exception("Database error")
                
                result, status_code = delete_favorite_fii(1)
                
                assert status_code == 500
                result_data = result.get_json()
                assert "Error in delete_favorite_fii" in result_data['message']

    def test_add_favorite_fii_success(self, app):
        """Test adding a favorite FII"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_favorite_query.filter_by.return_value.first.return_value = None
                mock_db_session.add = MagicMock()
                
                result, status_code = add_favorite_fii(1, 'KNRI11')
                
                assert status_code == 201
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite added successfully'

    def test_add_favorite_fii_already_exists(self, app):
        """Test adding a favorite FII that already exists"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.filter_by.return_value.first.return_value = MagicMock()
                
                result, status_code = add_favorite_fii(1, 'KNRI11')
                
                assert status_code == 400
                result_data = result.get_json()
                assert result_data['message'] == 'This FII is already favorited by this user'

    def test_add_favorite_fii_with_exception(self, app):
        """Test adding a favorite FII when an exception occurs"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_favorite_query.filter_by.return_value.first.return_value = None
                mock_db_session.add.side_effect = Exception("Database error")
                
                result, status_code = add_favorite_fii(1, 'KNRI11')
                
                assert status_code == 500
                result_data = result.get_json()
                assert "Error in add_favorite_fii" in result_data['message']

    def test_remove_favorite_fii_success(self, app):
        """Test removing a favorite FII"""
        with app.app_context():
            mock_favorite = MagicMock(spec=FavoriteFii)
            
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_favorite_query.filter_by.return_value.first.return_value = mock_favorite
                mock_db_session.delete = MagicMock()
                
                result, status_code = remove_favorite_fii(1, 'KNRI11')
                
                assert status_code == 200
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite deleted successfully'

    def test_remove_favorite_fii_not_found(self, app):
        """Test removing a favorite FII that doesn't exist"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query:
                mock_favorite_query.filter_by.return_value.first.return_value = None
                
                result, status_code = remove_favorite_fii(1, 'INVALID')
                
                assert status_code == 404
                result_data = result.get_json()
                assert result_data['message'] == 'Favorite not found'

    def test_remove_favorite_fii_with_exception(self, app):
        """Test removing a favorite FII when an exception occurs"""
        with app.app_context():
            with patch('services.favorite_fii_services.FavoriteFii.query') as mock_favorite_query, \
                 patch('services.favorite_fii_services.db.session') as mock_db_session:
                
                mock_favorite_query.filter_by.return_value.first.return_value = MagicMock()
                mock_db_session.delete.side_effect = Exception("Database error")
                
                result, status_code = remove_favorite_fii(1, 'KNRI11')
                
                assert status_code == 500
                result_data = result.get_json()
                assert "Error in remove_favorite_fii" in result_data['message']