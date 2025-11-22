# 🎯 Demo Queries & Examples

Use these example queries to test and showcase the CSV Analyzer AI Assistant!

## 📊 Basic Statistics

### Summary Statistics
```
Show me summary statistics for all numeric columns
```
**What it does:** Displays mean, median, std dev, min, max for each column

### Missing Values
```
Check for missing or null values in the dataset
```
**What it does:** Counts and shows percentage of missing values per column

### Data Shape
```
How many rows and columns are in this dataset?
```
**What it does:** Returns the dimensions of the dataset

## 📈 Visualizations

### Distribution Plots
```
Show me the distribution of vote_average
```
**What it does:** Creates a histogram showing value distribution

### Bar Charts
```
Show the top 10 movies by vote_average as a bar chart
```
**What it does:** Creates a horizontal bar chart of top values

### Time Series
```
Show how the average vote_average changed over the years
```
**What it does:** Groups by release year and plots trends

### Correlation Heatmap
```
Create a correlation heatmap for all numeric columns
```
**What it does:** Shows relationships between numerical variables

### Scatter Plots
```
Create a scatter plot of popularity vs vote_average
```
**What it does:** Plots relationship between two variables

### Pie Charts
```
Show the distribution of movies by original_language as a pie chart
```
**What it does:** Displays proportions in a pie chart

## 🔍 Data Exploration

### Top/Bottom N
```
Show me the top 20 most popular movies
```
**What it does:** Sorts and displays highest popularity values

### Filtering
```
Show movies with vote_average above 8.5
```
**What it does:** Filters data based on condition

### Grouping
```
Group movies by release year and show the count
```
**What it does:** Groups and aggregates data

### Unique Values
```
How many unique original languages are in the dataset?
```
**What it does:** Counts distinct values in a column

## 📊 Advanced Analysis

### Outlier Detection
```
Find outliers in the popularity column using IQR method
```
**What it does:** Identifies statistical outliers

### Trend Analysis
```
Show the trend of average vote_count over the years
```
**What it does:** Plots temporal trends

### Comparison
```
Compare average vote_average for movies before and after 2000
```
**What it does:** Groups and compares data segments

### Multi-variable Analysis
```
Create a box plot showing vote_average distribution by decade
```
**What it does:** Groups and shows distribution across categories

## 🎨 Complex Queries

### Multiple Plots
```
Create subplots showing:
1. Distribution of vote_average
2. Top 10 languages by movie count
3. Popularity vs vote_average scatter plot
```
**What it does:** Generates multiple visualizations in one figure

### Conditional Statistics
```
For movies released after 2010, show the top 5 languages by average vote_average
```
**What it does:** Filters, groups, and aggregates with conditions

### Time-based Grouping
```
Group movies by decade and show average popularity with a line chart
```
**What it does:** Custom time grouping with trend visualization

### Advanced Filtering
```
Show movies where vote_average > 8 AND vote_count > 1000, sorted by popularity
```
**What it does:** Multiple condition filtering with sorting

## 💡 Creative Queries

### Text Analysis
```
What are the most common words in movie titles?
```
**What it does:** Text processing and word frequency analysis

### Statistical Tests
```
Calculate the correlation between vote_count and popularity
```
**What it does:** Statistical correlation analysis

### Ranking
```
Create a ranking of the top 15 movies based on vote_average weighted by vote_count
```
**What it does:** Custom scoring and ranking

### Anomaly Detection
```
Find movies with unusually high popularity but low vote_average
```
**What it does:** Identifies interesting data points

## 🎬 Dataset-Specific Queries

These are specific to the included movies dataset:

### Language Analysis
```
Show the distribution of movies across different original languages
```

### Decade Trends
```
How has the average vote_average changed by decade?
```

### Popularity Analysis
```
What's the relationship between vote_count and popularity?
```

### Best Movies
```
Show the top 20 highest-rated movies (by vote_average) that have at least 500 votes
```

### Release Patterns
```
Show how many movies were released each year from 1950 to 2023
```

## 🧪 Testing Edge Cases

### Large Numbers
```
Show movies with popularity greater than 100
```

### Date Operations
```
Extract the year from release_date and show movies by decade
```

### String Operations
```
Show movies whose titles contain the word "love" or "Love"
```

### Multiple Aggregations
```
For each language, show count, average vote_average, and total vote_count
```

## 📝 Tips for Best Results

1. **Be Specific**: Instead of "show data", say "show the first 10 rows"
2. **Include Chart Type**: Explicitly mention "bar chart", "line plot", etc.
3. **Specify Columns**: Reference actual column names from your CSV
4. **Mention Limits**: Say "top 10", "first 20" to avoid overwhelming charts
5. **Combine Operations**: You can ask for filtering + sorting + visualization

## ⚠️ What NOT to Ask

- Don't ask to modify the original CSV file
- Don't request external data or API calls
- Don't ask for predictions without specifying method
- Avoid queries that would return thousands of rows without aggregation

## 🎓 Learning Path

Start simple and build up:

1. **Beginner**: "Show me the first 10 rows"
2. **Intermediate**: "Create a bar chart of top 10 movies by rating"
3. **Advanced**: "Group by decade, calculate average rating, and show trend with confidence intervals"

## 🚀 Pro Tips

- **Save Charts**: All charts are automatically saved to the `charts/` directory
- **Iterate**: Ask follow-up questions to refine your analysis
- **Experiment**: Try different visualization types for the same data
- **Combine**: Ask for multiple related analyses in one query

---

Have fun exploring your data! 🎉

