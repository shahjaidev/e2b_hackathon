# 🤝 Contributing to CSV Analyzer AI Assistant

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## 🎯 Ways to Contribute

- 🐛 Report bugs
- 💡 Suggest new features
- 📝 Improve documentation
- 🔧 Submit bug fixes
- ✨ Add new features
- 🎨 Improve UI/UX

## 🚀 Getting Started

1. **Fork the repository**
2. **Clone your fork**
   ```bash
   git clone https://github.com/your-username/e2b_hackathon.git
   cd e2b_hackathon
   ```

3. **Run the setup**
   ```bash
   ./setup.sh
   ```

4. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 📝 Development Guidelines

### Code Style

**Python (Backend)**
- Follow PEP 8 style guide
- Use meaningful variable names
- Add docstrings to functions
- Keep functions focused and small

**JavaScript (Frontend)**
- Use functional components
- Follow React best practices
- Use meaningful component names
- Add comments for complex logic

**CSS**
- Use consistent naming conventions
- Group related styles
- Add comments for sections
- Keep specificity low

### Testing

Before submitting:
- [ ] Test the upload functionality
- [ ] Test multiple query types
- [ ] Verify charts display correctly
- [ ] Check error handling
- [ ] Test on different browsers
- [ ] Verify mobile responsiveness

### Documentation

Update documentation when:
- Adding new features
- Changing APIs
- Modifying configuration
- Adding dependencies

## 🐛 Bug Reports

When reporting bugs, include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Detailed steps
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Screenshots**: If applicable
6. **Environment**:
   - OS version
   - Python version
   - Node.js version
   - Browser (if frontend issue)

**Example:**

```markdown
## Bug: Chart not displaying

**Description:** 
Chart image doesn't show after executing query.

**Steps:**
1. Upload dataset.csv
2. Ask "Show distribution of vote_average"
3. Code executes but no chart appears

**Expected:** Chart should display inline

**Actual:** Empty space where chart should be

**Environment:**
- macOS 14.0
- Python 3.11
- Chrome 120
```

## 💡 Feature Requests

When suggesting features:

1. **Use Case**: Why is this needed?
2. **Description**: What should it do?
3. **Implementation Ideas**: How might it work?
4. **Alternatives**: Other approaches considered?

## 🔧 Pull Requests

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] Branch is up to date with main

### PR Title Format

```
[Type] Brief description

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- style: Code style/formatting
- refactor: Code refactoring
- test: Adding tests
- chore: Maintenance
```

**Examples:**
- `feat: Add support for Excel files`
- `fix: Resolve chart rendering issue`
- `docs: Update setup instructions`

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing
How was this tested?

## Screenshots
If applicable

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass
```

## 🏗️ Project Structure

```
e2b_hackathon/
├── backend/
│   └── app.py          # Flask API - add endpoints here
├── frontend/
│   └── src/
│       ├── App.js      # Main component
│       └── App.css     # Styles
├── docs/               # Additional documentation
└── tests/              # Test files (to be added)
```

## 📚 Key Areas for Contribution

### High Priority

1. **Authentication System**
   - User login/signup
   - Session management
   - API key management

2. **Query History**
   - Save past queries
   - Rerun previous analyses
   - Export history

3. **Enhanced Visualizations**
   - More chart types
   - Interactive charts (Plotly)
   - Chart customization

### Medium Priority

1. **Data Export**
   - PDF reports
   - Excel export
   - CSV export

2. **Multiple File Support**
   - Upload multiple CSVs
   - Join/merge files
   - Switch between files

3. **Advanced Analysis**
   - Statistical tests
   - ML model training
   - Predictive analytics

### Low Priority

1. **UI Themes**
   - Dark mode
   - Custom themes
   - Accessibility improvements

2. **Mobile App**
   - React Native version
   - Native features

## 🧪 Testing Guidelines

### Manual Testing Checklist

**Upload Flow:**
- [ ] Drag and drop CSV
- [ ] Click to upload CSV
- [ ] Upload non-CSV file (should fail)
- [ ] Upload very large file
- [ ] Upload empty CSV

**Query Flow:**
- [ ] Simple statistics query
- [ ] Visualization query
- [ ] Complex analysis query
- [ ] Invalid query
- [ ] Very long query

**Error Handling:**
- [ ] Network error
- [ ] Invalid API key
- [ ] Code execution error
- [ ] Timeout handling

### Writing Tests

```python
# Backend test example
def test_upload_csv():
    """Test CSV upload endpoint"""
    with open('test_data.csv', 'rb') as f:
        response = client.post('/api/upload',
            data={'file': f, 'session_id': 'test'})
    assert response.status_code == 200
    assert 'filename' in response.json
```

```javascript
// Frontend test example
test('renders upload area', () => {
  render(<App />);
  const uploadText = screen.getByText(/Upload Your CSV/i);
  expect(uploadText).toBeInTheDocument();
});
```

## 📖 Documentation Standards

### Code Comments

```python
def process_query(message: str, session_id: str) -> dict:
    """
    Process a user query and return analysis results.
    
    Args:
        message: The user's natural language query
        session_id: Unique identifier for the session
        
    Returns:
        dict: Response containing code, results, and charts
        
    Raises:
        ValueError: If session_id is invalid
        APIError: If Gemini API call fails
    """
```

### README Updates

When adding features:
1. Update feature list
2. Add usage examples
3. Update setup if needed
4. Add troubleshooting tips

## 🔍 Code Review Process

All PRs will be reviewed for:
- Code quality
- Functionality
- Documentation
- Tests
- Performance
- Security

## 🎓 Learning Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [React Documentation](https://react.dev/)
- [Gemini API Docs](https://ai.google.dev/docs)
- [E2B Documentation](https://e2b.dev/docs)
- [Pandas Documentation](https://pandas.pydata.org/docs/)

## 🏅 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in documentation

## 📞 Questions?

- Open a discussion on GitHub
- Check existing issues
- Review documentation

## 📜 License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT).

---

Thank you for making CSV Analyzer AI Assistant better! 🎉

